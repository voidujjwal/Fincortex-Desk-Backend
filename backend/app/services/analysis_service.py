"""Analysis service - orchestrates the full analysis workflow.

Handles daily limits, background execution, result persistence,
WebSocket progress streaming, and coordinates between the TradingAgents
wrapper, queue, and DB.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from app.config.settings import Settings, get_settings
from app.database import get_supabase_client
from app.database.repositories.analysis_repo import AnalysisRepository
from app.database.repositories.analysis_event_repo import AnalysisEventRepository
from app.database.repositories.agent_report_repo import AgentReportRepository
from app.database.repositories.usage_repo import UsageRepository
from app.queue import AsyncioJobQueue, Job
from app.services.trading_agents_service import TradingAgentsService
from app.services.news_service import NewsService
from app.utils.helpers import generate_job_id, utc_now
from app.websocket import ws_manager

logger = logging.getLogger("tradingagents.services")

AGENT_NAMES = {
    "market_report": "technical",
    "sentiment_report": "sentiment",
    "news_report": "news",
    "fundamentals_report": "fundamental",
}


class AnalysisService:
    """Service that orchestrates analysis execution."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        queue: Optional[AsyncioJobQueue] = None,
    ):
        self.settings = settings or get_settings()
        self.supabase = get_supabase_client(self.settings)
        self.analysis_repo = AnalysisRepository(self.supabase)
        self.event_repo = AnalysisEventRepository(self.supabase)
        self.agent_report_repo = AgentReportRepository(self.supabase)
        self.usage_repo = UsageRepository(self.supabase)
        self.trading_service = TradingAgentsService()
        self.news_service = NewsService(settings)
        self.queue = queue or AsyncioJobQueue()

    async def start_analysis(
        self,
        user_id: str,
        ticker: str,
        models: dict[str, str],
        email: str = "",
        selected_analysts: Optional[list[str]] = None,
        max_debate_rounds: int = 1,
        max_risk_discuss_rounds: int = 1,
        analysis_date: Optional[str] = None,
    ) -> dict:
        """Start a new analysis job.

        Checks daily limits for free users, creates the DB record,
        enqueues the background job, and returns immediately with a job_id.
        """
        logger.info(
            "Starting analysis request user=%s ticker=%s models=%s",
            user_id,
            ticker,
            models,
        )

        plan = await self._get_user_plan(user_id)
        logger.info("Plan check for user %s: %s", user_id, plan)

        await self._ensure_profile_exists(user_id, email)

        if plan.lower() == "free":
            used = 0
            try:
                used = await self.usage_repo.get_today_usage(user_id)
            except Exception as exc:
                logger.warning(
                    "Usage check failed for user %s (schema mismatch?): %s",
                    user_id,
                    exc,
                )
            logger.info(
                "Usage check for user %s: %d/%d",
                user_id,
                used,
                self.settings.free_daily_limit,
            )
            if used >= self.settings.free_daily_limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily limit of {self.settings.free_daily_limit} analyses reached for Free plan",
                )

        job_id = generate_job_id()
        market = ticker.split(".")[-1].upper() if "." in ticker else "US"
        now = utc_now().isoformat()
        if analysis_date:
            try:
                analysis_date = datetime.fromisoformat(analysis_date).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                analysis_date = None
        if not analysis_date:
            analysis_date = utc_now().strftime("%Y-%m-%d")
        analysis_data = {
            "id": job_id,
            "user_id": user_id,
            "ticker": ticker,
            "company_name": ticker,
            "market": market,
            "analysis_date": analysis_date,
            "status": "pending",
            "selected_models": models,
            "created_at": now,
            "updated_at": now,
        }
        await self.analysis_repo.insert(analysis_data)
        logger.info("DB insert into analyses succeeded: %s", job_id)

        # Register the researched stock as a news interest (best-effort)
        await self.news_service.add_interest(
            user_id, ticker, market, source="research"
        )

        if plan.lower() == "free":
            try:
                await self.usage_repo.record_usage(user_id, job_id)
                logger.info("Usage recorded for user %s job %s", user_id, job_id)
            except Exception as exc:
                logger.warning(
                    "Usage record failed for user %s (schema mismatch?): %s",
                    user_id,
                    exc,
                )

        job = Job(
            job_id=job_id,
            task=lambda: self._execute_analysis(
                job_id=job_id,
                user_id=user_id,
                ticker=ticker,
                models=models,
                selected_analysts=selected_analysts,
                max_debate_rounds=max_debate_rounds,
                max_risk_discuss_rounds=max_risk_discuss_rounds,
                analysis_date=analysis_date,
            ),
        )
        await self.queue.enqueue(job)
        logger.info("Job %s enqueued for background execution", job_id)

        return {"job_id": job_id, "status": "pending"}

    async def get_analysis(self, job_id: str) -> Optional[dict]:
        """Get the complete analysis report mapped for frontend compatibility."""
        result = await self.analysis_repo.get_by_job_id(job_id)
        if not result:
            return None
        if "id" in result:
            result["job_id"] = result.get("id")

        await self._merge_agent_reports(result)
        return self._format_analysis_detail(result)

    async def get_events(self, job_id: str) -> list:
        """Get streaming events for an analysis."""
        try:
            return await self.event_repo.get_by_analysis_id(job_id)
        except Exception:
            return []

    @staticmethod
    def _extract_decision(text: str) -> str:
        """Map an LLM verdict string to a BUY/SELL/HOLD decision."""
        t = (text or "").upper()
        if not t:
            return "HOLD"
        for marker in (
            "FINAL TRANSACTION PROPOSAL",
            "FINAL TRANSACTION",
            "RECOMMENDATION:",
            "RECOMMENDED ACTION",
            "VERDICT:",
        ):
            idx = t.find(marker)
            if idx != -1:
                seg = t[idx:idx + 300]
                if any(w in seg for w in ("SELL", "REDUCE", "TRIM", "EXIT", "UNDERWEIGHT")):
                    return "SELL"
                if any(w in seg for w in ("BUY", "ADD", "ACCUMULATE", "OVERWEIGHT")):
                    return "BUY"
                if any(w in seg for w in ("HOLD", "NEUTRAL", "EQUAL-WEIGHT", "STAY")):
                    return "HOLD"
        if any(w in t for w in ("SELL", "REDUCE", "TRIM", "EXIT", "UNDERWEIGHT")):
            return "SELL"
        if any(w in t for w in ("BUY", "ACCUMULATE", "OVERWEIGHT")):
            return "BUY"
        return "HOLD"

    def _format_analysis_detail(self, result: dict) -> dict:
        """Map backend database records into structured frontend fields."""
        models_sel = result.get("selected_models") or result.get("model_selection") or {}
        status = result.get("status", "pending")

        # Format agent outputs
        m_rep = result.get("market_report")
        f_rep = result.get("fundamentals_report")
        n_rep = result.get("news_report")
        s_rep = result.get("sentiment_report")

        agent_outputs = {
            "technical": {
                "status": "completed" if m_rep else (status if status in ["running", "pending"] else "idle"),
                "model": models_sel.get("technical", models_sel.get("quick_think_llm", "gpt-5-mini")),
                "content": m_rep or ("Waiting for technical analysis report..." if status == "running" else ""),
                "progress": 100 if m_rep else (30 if status == "running" else 0),
            },
            "fundamental": {
                "status": "completed" if f_rep else (status if status in ["running", "pending"] else "idle"),
                "model": models_sel.get("fundamental", models_sel.get("deep_think_llm", "gpt-5.2")),
                "content": f_rep or ("Waiting for fundamental analysis report..." if status == "running" else ""),
                "progress": 100 if f_rep else (30 if status == "running" else 0),
            },
            "news": {
                "status": "completed" if n_rep else (status if status in ["running", "pending"] else "idle"),
                "model": models_sel.get("news", models_sel.get("quick_think_llm", "gpt-5-mini")),
                "content": n_rep or ("Waiting for news analysis report..." if status == "running" else ""),
                "progress": 100 if n_rep else (30 if status == "running" else 0),
            },
            "social": {
                "status": "completed" if s_rep else (status if status in ["running", "pending"] else "idle"),
                "model": models_sel.get("social", models_sel.get("quick_think_llm", "gpt-5-mini")),
                "content": s_rep or ("Waiting for social sentiment analysis report..." if status == "running" else ""),
                "progress": 100 if s_rep else (30 if status == "running" else 0),
            },
        }

        # If analysis is not completed yet, return clean empty structures without dummy decision
        if status != "completed":
            result.update({
                "agent_outputs": agent_outputs,
                "debate": {},
                "trader": {},
                "risk_manager": {},
                "verdict": {},
                "decision": None,
                "confidence": None,
                "risk_score": None,
                "risk_level": None,
                "models_used": list(models_sel.values()) if models_sel else [],
                "model_selection": models_sel,
            })
            return result

        # Format decision and verdict when COMPLETED
        decision_raw = (result.get("decision") or result.get("final_trade_decision") or "").upper()
        if not decision_raw:
            # Can't determine decision yet — treat as not completed
            result.update({
                "agent_outputs": agent_outputs,
                "debate": {},
                "trader": {},
                "risk_manager": {},
                "verdict": {},
                "decision": None,
                "confidence": None,
                "risk_score": None,
                "risk_level": None,
                "models_used": list(models_sel.values()) if models_sel else [],
                "model_selection": models_sel,
            })
            return result

        trader_plan = result.get("trader_investment_plan") or result.get("investment_plan") or {}
        trader_text = str(trader_plan.get("reasoning", trader_plan)) if isinstance(trader_plan, dict) else str(trader_plan)
        trader_confidence = None
        if isinstance(trader_plan, dict) and trader_plan.get("confidence") is not None:
            raw_conf = trader_plan["confidence"]
            if isinstance(raw_conf, (int, float)):
                trader_confidence = float(raw_conf)
            else:
                conf_match = re.search(r"(\d{1,3})", str(raw_conf))
                if conf_match:
                    trader_confidence = float(conf_match.group(1))
        if trader_confidence is None:
            conf_match = re.search(
                r"confidence\s*(?:score)?\s*[:=]?\s*[^0-9]*?(\d{1,3})\s*(?:%\s*\**|percent)",
                trader_text,
                re.IGNORECASE,
            )
            if conf_match:
                trader_confidence = float(conf_match.group(1))
        if trader_confidence is None:
            trader_confidence = 75
        trader_confidence = min(max(trader_confidence, 0), 100)

        # The trader's final proposal is the most authoritative signal; fall back
        # to the stored decision (e.g. "UNDERWEIGHT") which maps to SELL.
        plan_text = str(result.get("trader_investment_plan") or "") + " " + str(result.get("investment_plan") or "")
        decision = (
            self._extract_decision(plan_text)
            if plan_text.strip()
            else self._extract_decision(decision_raw)
        )

        # Extract risk data from risk_debate_state if available
        risk_state = result.get("risk_debate_state") or {}
        risk_judge = risk_state.get("judge_decision", "") if isinstance(risk_state, dict) else ""
        risk_score = None
        m = re.search(r"risk\s*score\s*[:=]?\s*(\d{1,3})\s*(?:/\s*100)?", risk_judge, re.IGNORECASE)
        if m:
            risk_score = min(int(m.group(1)), 100)
        if risk_score is None:
            m = re.search(r"(\d{1,3})\s*/\s*100", risk_judge)
            if m:
                risk_score = min(int(m.group(1)), 100)
        if risk_score is not None:
            risk_level_str = "High" if risk_score >= 60 else ("Medium" if risk_score >= 40 else "Low")
        else:
            risk_level_map = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
            risk_level_str = "Medium"
            for k, v in risk_level_map.items():
                if k in risk_judge.lower():
                    risk_level_str = v
                    break
            if risk_level_str == "Medium":
                rating_map = {
                    "underweight": 70,
                    "overweight": 35,
                    "sell": 85,
                    "buy": 20,
                    "hold": 50,
                    "neutral": 50,
                }
                for k, v in rating_map.items():
                    if k in risk_judge.lower():
                        risk_level_str = "High" if v >= 60 else ("Medium" if v >= 40 else "Low")
                        risk_score = v
                        break
            if risk_score is None:
                risk_score_map = {"Low": 25, "Medium": 50, "High": 75, "Critical": 90}
                risk_score = risk_score_map.get(risk_level_str, 50)

        # Extract debate data (histories are plain strings in this graph version)
        debate_state = result.get("investment_debate_state") or {}
        bull_history = debate_state.get("bull_history") or "" if isinstance(debate_state, dict) else ""
        bear_history = debate_state.get("bear_history") or "" if isinstance(debate_state, dict) else ""
        judge_decision = debate_state.get("judge_decision", "") if isinstance(debate_state, dict) else ""

        def _debate_text(history: str) -> str:
            if not history:
                return ""
            if isinstance(history, list):
                return " ".join(str(h) for h in history[-3:])
            # Send the full debate text; the frontend parses it into turns.
            return str(history)

        bull_content = _debate_text(bull_history)
        bear_content = _debate_text(bear_history)
        has_debate = bool(bull_content or bear_content or judge_decision)
        debate_winner = "bull" if decision == "BUY" else ("bear" if decision == "SELL" else "tie")
        debate_summary = judge_decision[:500] if judge_decision else f"Debate concluded in favor of {decision} decision."

        has_risk = bool(result.get("risk_debate_state"))
        has_trader = bool(trader_plan)

        trader_full = result.get("trader_full_report") or {}
        trader_full_plan = str(trader_full.get("trader_investment_plan") or "") if isinstance(trader_full, dict) else ""
        trader_full_judgment = str(
            trader_full.get("investment_plan") or trader_full.get("judge_decision") or ""
        ) if isinstance(trader_full, dict) else ""

        trader_output = {
            "decision": decision,
            "confidence": int(trader_confidence),
            "reasoning": trader_text or "Multi-agent consensus recommendation.",
            "riskReward": trader_plan.get("risk_reward", "1:2") if isinstance(trader_plan, dict) else "1:2",
            "timeHorizon": result.get("investment_horizon", "Swing"),
            "plan": trader_full_plan,
            "judgment": trader_full_judgment,
            "report": trader_full_judgment + ("\n\n" if trader_full_judgment and trader_full_plan else "") + trader_full_plan,
        }

        risk_output = {
            "riskScore": risk_score,
            "riskLevel": risk_level_str,
            "portfolioRecommendation": risk_judge[:500] if risk_judge else "Maintain standard position sizing with stop-loss protection.",
            "positionSizeSuggestion": "5-10% of portfolio",
            "warnings": ["Monitor volatility around upcoming earnings/macro announcements"],
            "judgment": risk_judge,
        }

        debate_output = {
            "bull": {
                "status": "completed",
                "model": models_sel.get("debate_bull", "claude-sonnet-4-6"),
                "content": bull_content,
                "arguments": ["Strong revenue momentum", "Healthy technical support levels"],
                "confidence": 85,
            },
            "bear": {
                "status": "completed",
                "model": models_sel.get("debate_bear", "claude-sonnet-4-6"),
                "content": bear_content,
                "arguments": ["Macro valuation pressure", "Short-term momentum resistance"],
                "confidence": 40,
            },
            "winner": debate_winner,
            "summary": debate_summary,
            "judgeDecision": judge_decision,
        }

        stored_verdict = result.get("verdict") or {}
        stored_summary = stored_verdict.get("summary") if isinstance(stored_verdict, dict) else ""
        verdict_summary = (
            str(stored_summary)
            or result.get("summary")
            or (f"{decision} — {int(trader_confidence)}% confidence, {risk_level_str} risk")
        )
        verdict_judgment = "\n\n".join(
            part for part in (trader_full_judgment, risk_judge) if part
        ) or str(result.get("summary") or "")
        verdict_output = {
            "decision": decision,
            "confidence": int(trader_confidence),
            "riskLevel": risk_level_str,
            "summary": verdict_summary,
            "bullScore": 85,
            "bearScore": 40,
            "judgment": verdict_judgment,
        }

        result.update({
            "agent_outputs": agent_outputs,
            "debate": debate_output if has_debate else {},
            "trader": trader_output if has_trader else {},
            "risk_manager": risk_output if has_risk else {},
            "verdict": verdict_output,
            "decision": decision,
            "confidence": int(trader_confidence),
            "risk_score": risk_score,
            "risk_level": risk_level_str,
            "models_used": list(models_sel.values()) if models_sel else ["gpt-5-mini", "claude-sonnet-4-6"],
            "model_selection": models_sel,
        })
        return result

    async def get_history(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> dict:
        """Get paginated analysis history."""
        items = await self.analysis_repo.list_by_user(
            user_id, page, page_size
        )
        formatted_items = []
        for item in items:
            if "id" in item:
                item["job_id"] = item.get("id")
            await self._merge_agent_reports(item)
            formatted_items.append(self._format_analysis_detail(item))
        total = await self.analysis_repo.count_by_user(user_id)
        return {
            "items": formatted_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
        }

    async def get_models(self) -> dict:
        """Return available models formatted for frontend."""
        formatted_models = [
            # OpenAI
            {"id": "gpt-5-mini", "label": "GPT-5 Mini - Balanced speed, cost, and capability", "provider": "OpenAI"},
            {"id": "gpt-5-nano", "label": "GPT-5 Nano - High-throughput, simple tasks", "provider": "OpenAI"},
            {"id": "gpt-5.4", "label": "GPT-5.4 - Latest frontier, 1M context", "provider": "OpenAI"},
            {"id": "gpt-4.1", "label": "GPT-4.1 - Smartest non-reasoning model", "provider": "OpenAI"},
            # Anthropic
            {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6 - Best speed and intelligence balance", "provider": "Anthropic"},
            {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5 - Fast, near-instant responses", "provider": "Anthropic"},
            {"id": "claude-sonnet-4-5", "label": "Claude Sonnet 4.5 - Agents and coding", "provider": "Anthropic"},
            # Google
            {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash - Next-gen fast", "provider": "Google"},
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash - Balanced, stable", "provider": "Google"},
            {"id": "gemini-3.1-flash-lite-preview", "label": "Gemini 3.1 Flash Lite - Most cost-efficient", "provider": "Google"},
            {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite - Fast, low-cost", "provider": "Google"},
            # xAI
            {"id": "grok-4-1-fast-non-reasoning", "label": "Grok 4.1 Fast (Non-Reasoning) - Speed optimized, 2M ctx", "provider": "xAI"},
            {"id": "grok-4-fast-non-reasoning", "label": "Grok 4 Fast (Non-Reasoning) - Speed optimized", "provider": "xAI"},
            {"id": "grok-4-1-fast-reasoning", "label": "Grok 4.1 Fast (Reasoning) - High-performance, 2M ctx", "provider": "xAI"},
            # NVIDIA
            {"id": "nvidia/nemotron-3-super-120b-a12b", "label": "NVIDIA Nemotron 3 Super 120B (free)", "provider": "NVIDIA"},
            {"id": "nvidia/nemotron-3-nano-30b-a3b", "label": "NVIDIA Nemotron 3 Nano 30B (free)", "provider": "NVIDIA"},
            {"id": "nvidia/nemotron-3-ultra-550b-a55b", "label": "NVIDIA Nemotron 3 Ultra (free)", "provider": "NVIDIA"},
            {"id": "nvidia/llama-3.1-nemotron-70b-instruct", "label": "NVIDIA Llama 3.1 Nemotron 70B (free)", "provider": "NVIDIA"},
            {"id": "meta/llama-3.3-70b-instruct", "label": "Meta Llama 3.3 70B (NVIDIA, free)", "provider": "NVIDIA"},
            # OpenRouter
            {"id": "z-ai/glm-4.5-air", "label": "Z.AI GLM 4.5 Air (free)", "provider": "OpenRouter"},
            {"id": "poolside/laguna-s-2.1:free", "label": "Laguna S 2.1 (free)", "provider": "OpenRouter"},
            # Ollama
            {"id": "qwen3:latest", "label": "Qwen3:latest (8B, local)", "provider": "Ollama"},
            {"id": "gpt-oss:latest", "label": "GPT-OSS:latest (20B, local)", "provider": "Ollama"},
            {"id": "glm-4.7-flash:latest", "label": "GLM-4.7-Flash:latest (30B, local)", "provider": "Ollama"},
        ]
        agent_keys = [
            "quick_think", "deep_think",
            "fundamental", "technical", "news", "social", "sentiment",
            "debate_bull", "debate_bear", "trader", "risk_manager"
        ]
        res = {"models": formatted_models}
        for k in agent_keys:
            res[k] = formatted_models
        return res

    async def get_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile."""
        from app.database.repositories.profile_repo import ProfileRepository

        repo = ProfileRepository(self.supabase)
        return await repo.get_by_user_id(user_id)

    async def update_profile(self, user_id: str, data: dict) -> Optional[dict]:
        """Update user profile."""
        from app.database.repositories.profile_repo import ProfileRepository

        repo = ProfileRepository(self.supabase)
        existing = await repo.get_by_user_id(user_id)
        if existing:
            return await repo.update(existing["id"], data)
        return None

    async def get_settings(self, user_id: str) -> Optional[dict]:
        """Get user settings."""
        from app.database.repositories.settings_repo import SettingsRepository

        repo = SettingsRepository(self.supabase)
        return await repo.get_by_user_id(user_id)

    async def update_settings(self, user_id: str, data: dict) -> Optional[dict]:
        """Update user settings."""
        from app.database.repositories.settings_repo import SettingsRepository

        repo = SettingsRepository(self.supabase)
        return await repo.upsert(user_id, data)

    async def get_usage(self, user_id: str) -> dict:
        """Get today's usage for a user."""
        used = await self.usage_repo.get_today_usage(user_id)
        plan = await self._get_user_plan(user_id)
        limit = self.settings.free_daily_limit if plan.lower() == "free" else 999
        return {
            "used_today": used,
            "remaining": max(0, limit - used),
            "daily_limit": limit,
        }

    async def _get_user_plan(self, user_id: str) -> str:
        """Get the user's plan from the profiles table."""
        try:
            profile = await self.get_profile(user_id)
            if profile:
                return profile.get("plan", "Free")
        except Exception as exc:
            logger.warning("Profile lookup failed (schema mismatch?): %s", exc)
        return "Free"

    async def _ensure_profile_exists(self, user_id: str, email: str = "") -> None:
        """Ensure a profile row exists for this user (FK requirement)."""
        try:
            from app.database.repositories.profile_repo import ProfileRepository
            repo = ProfileRepository(self.supabase)
            profile = await repo.ensure_exists(user_id, email=email)
            logger.info("Profile ready for user %s: %s", user_id, profile.get("id"))
        except Exception as exc:
            logger.warning("Failed to ensure profile for %s: %s", user_id, exc)

    async def _safe_insert(self, table: str, data: dict) -> Optional[dict]:
        """Insert a record, catching schema/DB errors gracefully."""
        try:
            result = self.analysis_repo._table.insert(data).execute()
            if result.data:
                logger.info("DB insert into %s succeeded: %s", table, result.data[0].get("id"))
                return result.data[0]
            logger.warning("DB insert into %s returned no data (no error)", table)
            return None
        except Exception as exc:
            logger.error("DB insert into %s failed: %s", table, exc)
            return None

    async def _safe_update(self, job_id: str, data: dict) -> None:
        """Update a record, catching schema/DB errors gracefully."""
        try:
            await self.analysis_repo.update(job_id, data)
        except Exception as exc:
            logger.error("DB update for %s failed: %s", job_id, exc)

    async def _execute_analysis(
        self,
        job_id: str,
        user_id: str,
        ticker: str,
        models: dict[str, str],
        selected_analysts: Optional[list[str]],
        max_debate_rounds: int,
        max_risk_discuss_rounds: int,
        analysis_date: Optional[str] = None,
    ) -> None:
        """Execute the analysis in the background."""
        t_start = time.monotonic()
        logger.info("[%s] Background execution started for %s", job_id, ticker)

        try:
            await self.analysis_repo.update(job_id, {"status": "running"})
            logger.info("[%s] Status updated to running", job_id)

            await self._emit_event(
                job_id,
                "bull",
                "running",
                f"Starting analysis for {ticker}",
                0.0,
            )
            logger.info("[%s] System event emitted", job_id)

            result = await self.trading_service.run_analysis(
                job_id=job_id,
                ticker=ticker,
                models=models,
                selected_analysts=selected_analysts,
                max_debate_rounds=max_debate_rounds,
                max_risk_discuss_rounds=max_risk_discuss_rounds,
                analysis_date=analysis_date,
                progress_callback=self._make_progress_callback(job_id),
            )

            final_state = result["final_state"]
            decision = result.get("decision")
            exec_time = result.get("execution_time_seconds", 0)
            total_time = result.get("total_time_seconds", 0)

            logger.info(
                "[%s] TradingAgents completed in %.2fs, persisting results",
                job_id,
                total_time,
            )

            await self._persist_agent_reports(job_id, final_state)
            logger.info("[%s] Agent reports persisted", job_id)

            await self._persist_report_columns(job_id, final_state)
            logger.info("[%s] Report columns persisted", job_id)

            await self._persist_events(job_id, final_state)
            logger.info("[%s] Events persisted", job_id)

            await self._persist_debate(job_id, final_state)
            await self._persist_risk_assessment(job_id, final_state)
            await self._persist_trader_decision(job_id, final_state)

            await self.analysis_repo.update(job_id, {
                "status": "completed",
                "decision": decision,
                "summary": str(final_state.get("final_trade_decision") or decision or "")[:1000],
                "execution_time": round(exec_time, 2),
                "completed_at": utc_now().isoformat(),
            })
            logger.info("[%s] Analysis marked as completed", job_id)

        except asyncio.TimeoutError as exc:
            logger.error("[%s] TIMEOUT: %s", job_id, exc)
            await self.analysis_repo.update(job_id, {
                "status": "failed",
                "completed_at": utc_now().isoformat(),
            })
            await self._emit_event(
                job_id, "bull", "failed", str(exc), 0.0
            )

        except Exception as exc:
            logger.error("[%s] FAILED: %s", job_id, exc, exc_info=True)
            await self.analysis_repo.update(job_id, {
                "status": "failed",
                "completed_at": utc_now().isoformat(),
            })
            await self._emit_event(
                job_id, "bull", "failed", str(exc), 0.0
            )
        finally:
            total_elapsed = time.monotonic() - t_start
            logger.info(
                "[%s] Background execution finished in %.2fs total",
                job_id,
                total_elapsed,
            )

    def _make_progress_callback(self, job_id: str):
        """Create a progress callback that pushes updates to WebSocket clients.

        Called from sync context (asyncio.to_thread), so we dispatch
        the async WebSocket send via run_coroutine_threadsafe.
        """
        loop = asyncio.get_event_loop()

        def callback(progress: float, agent_name: str):
            try:
                asyncio.run_coroutine_threadsafe(
                    ws_manager.send_progress(job_id, agent_name, progress),
                    loop,
                )
            except Exception:
                logger.debug("[%s] WebSocket progress update failed", job_id)

        return callback

    async def _emit_event(
        self,
        job_id: str,
        agent: str,
        status: str,
        content: str = "",
        progress: float = 0.0,
    ) -> None:
        """Insert a streaming event into the database."""
        try:
            await self.event_repo.insert({
                "analysis_id": job_id,
                "agent": agent,
                "status": status,
                "message": content,
                "progress": progress,
                "timestamp": utc_now().isoformat(),
            })
        except Exception as exc:
            logger.error("[%s] Failed to insert event: %s", job_id, exc)

    async def _persist_agent_reports(self, job_id: str, final_state: dict) -> None:
        """Persist agent reports and structured debate/risk/trader results.

        Analyst reports are stored as markdown rows; the debate/risk states are
        stored as JSON rows so the API can reconstruct the full analysis.
        """
        reports = []
        timestamp = utc_now().isoformat()

        for field, agent_name in AGENT_NAMES.items():
            content = final_state.get(field, "")
            if content:
                reports.append({
                    "analysis_id": job_id,
                    "agent_name": agent_name,
                    "markdown_report": str(content),
                    "created_at": timestamp,
                })

        debate_state = final_state.get("investment_debate_state") or {}
        risk_state = final_state.get("risk_debate_state") or {}
        if debate_state:
            reports.append({
                "analysis_id": job_id,
                "agent_name": "bull",
                "markdown_report": json.dumps({
                    "history": debate_state.get("bull_history", ""),
                    "current_response": debate_state.get("current_response", ""),
                }),
                "created_at": timestamp,
            })
            reports.append({
                "analysis_id": job_id,
                "agent_name": "bear",
                "markdown_report": json.dumps({
                    "history": debate_state.get("bear_history", ""),
                    "current_response": debate_state.get("current_response", ""),
                }),
                "created_at": timestamp,
            })
            reports.append({
                "analysis_id": job_id,
                "agent_name": "trader",
                "markdown_report": json.dumps({
                    "trader_investment_plan": final_state.get("trader_investment_plan", ""),
                    "investment_plan": final_state.get("investment_plan", ""),
                    "judge_decision": debate_state.get("judge_decision", ""),
                }),
                "created_at": timestamp,
            })
        if risk_state:
            reports.append({
                "analysis_id": job_id,
                "agent_name": "risk",
                "markdown_report": json.dumps(risk_state),
                "created_at": timestamp,
            })

        if reports:
            try:
                await self.agent_report_repo.insert_batch(reports)
            except Exception as exc:
                logger.error("[%s] Failed to persist agent reports: %s", job_id, exc)

    async def _persist_report_columns(self, job_id: str, final_state: dict) -> None:
        """Store each report and debate side in its own analyses column.

        New jobs are fully self-contained on the analyses row (report columns,
        bull/bear debate columns, trader and risk manager decision columns,
        numeric risk score/confidence, plus the JSONB frontend views). Older
        jobs without these columns keep working via the agent_reports fallback.
        """
        try:
            debate_state = final_state.get("investment_debate_state") or {}
            risk_state = final_state.get("risk_debate_state") or {}

            updates: dict = {}
            for field in ("market_report", "sentiment_report", "news_report", "fundamentals_report"):
                content = final_state.get(field, "")
                if content:
                    updates[field] = str(content)

            if debate_state:
                for key, column in (
                    ("bull_history", "bull_debate"),
                    ("bear_history", "bear_debate"),
                    ("judge_decision", "judge_decision"),
                ):
                    if debate_state.get(key):
                        updates[column] = str(debate_state.get(key))
            if final_state.get("trader_investment_plan"):
                updates["trader_investment_plan"] = str(final_state["trader_investment_plan"])
            if final_state.get("investment_plan"):
                updates["investment_plan"] = str(final_state["investment_plan"])
            if risk_state and risk_state.get("judge_decision"):
                updates["risk_manager_decision"] = str(risk_state.get("judge_decision"))

            if updates:
                await self.analysis_repo.update(job_id, updates)
            logger.info("[%s] Report columns updated: %s", job_id, sorted(updates.keys()))
        except Exception as exc:
            logger.error("[%s] Failed to persist report columns: %s", job_id, exc)

        try:
            row = await self.analysis_repo.get_by_job_id(job_id)
            if not row:
                return
            fmt = dict(row)
            for field in ("market_report", "sentiment_report", "news_report", "fundamentals_report"):
                content = final_state.get(field) or fmt.get(field) or ""
                if content:
                    fmt[field] = str(content)
            fmt["investment_debate_state"] = debate_state or fmt.get("investment_debate_state") or {}
            fmt["risk_debate_state"] = risk_state or fmt.get("risk_debate_state") or {}
            fmt["trader_investment_plan"] = final_state.get("trader_investment_plan") or fmt.get("trader_investment_plan") or ""
            fmt["investment_plan"] = final_state.get("investment_plan") or fmt.get("investment_plan") or ""
            fmt["status"] = "completed"
            # The analyses row's decision is written after this method runs, so
            # derive it from the graph state to avoid the empty early-return.
            fmt["decision"] = fmt.get("decision") or str(final_state.get("final_trade_decision") or "")

            formatted = self._format_analysis_detail(fmt)
            risk_level = formatted.get("risk_level")
            if risk_level:
                risk_level = str(risk_level).lower()
            await self.analysis_repo.update(job_id, {
                "agent_outputs": formatted.get("agent_outputs") or {},
                "debate": formatted.get("debate") or {},
                "trader": formatted.get("trader") or {},
                "risk_manager": formatted.get("risk_manager") or {},
                "verdict": formatted.get("verdict") or {},
                "risk_score": formatted.get("risk_score"),
                "risk_level": risk_level,
                "confidence": formatted.get("confidence"),
            })
        except Exception as exc:
            logger.error("[%s] Failed to persist analysis view columns: %s", job_id, exc)

    async def _merge_agent_reports(self, result: dict) -> dict:
        """Merge persisted agent report rows into the analyses record.

        New-style jobs store each report/debate side/risk decision in their own
        analyses columns (job-id keyed) — those take priority. Older jobs fall
        back to the agent_reports table so nothing breaks for historical runs.
        """
        # Column-based values (new-style jobs) always win over the fallback.
        if result.get("bull_debate"):
            (result.setdefault("investment_debate_state", {}))["bull_history"] = result["bull_debate"]
        if result.get("bear_debate"):
            (result.setdefault("investment_debate_state", {}))["bear_history"] = result["bear_debate"]
        if result.get("judge_decision"):
            (result.setdefault("investment_debate_state", {}))["judge_decision"] = result["judge_decision"]
        if result.get("trader_investment_plan"):
            result["trader_investment_plan"] = result["trader_investment_plan"]
        if result.get("investment_plan"):
            result["investment_plan"] = result["investment_plan"]
        if result.get("risk_manager_decision"):
            result["risk_debate_state"] = result.get("risk_debate_state") or {}
            result["risk_debate_state"]["judge_decision"] = result["risk_manager_decision"]

        try:
            rows = await self.agent_report_repo.get_by_analysis_id(
                result.get("id") or result.get("job_id") or ""
            )
        except Exception as exc:
            logger.warning(
                "[%s] Failed to load agent reports: %s",
                result.get("id"),
                exc,
            )
            return result

        field_map = {
            "technical": "market_report",
            "sentiment": "sentiment_report",
            "news": "news_report",
            "fundamental": "fundamentals_report",
            "social": "sentiment_report",
        }
        debate_state = result.get("investment_debate_state") or {}
        for row in rows:
            name = row.get("agent_name")
            content = row.get("markdown_report")
            if not content:
                continue
            if name in field_map:
                if not result.get(field_map[name]):
                    result[field_map[name]] = content
            elif name in ("bull", "bear"):
                try:
                    payload = json.loads(content)
                except (ValueError, TypeError):
                    payload = {}
                history = payload.get("history") or content
                if name == "bull":
                    if not debate_state.get("bull_history"):
                        debate_state["bull_history"] = history
                else:
                    if not debate_state.get("bear_history"):
                        debate_state["bear_history"] = history
            elif name == "trader":
                try:
                    payload = json.loads(content)
                except (ValueError, TypeError):
                    payload = {}
                result["trader_full_report"] = payload
                if payload.get("trader_investment_plan") and not result.get("trader_investment_plan"):
                    result["trader_investment_plan"] = payload["trader_investment_plan"]
                if payload.get("investment_plan") and not result.get("investment_plan"):
                    result["investment_plan"] = payload["investment_plan"]
                if payload.get("judge_decision") and not debate_state.get("judge_decision"):
                    debate_state["judge_decision"] = payload["judge_decision"]
            elif name == "risk":
                try:
                    payload = json.loads(content)
                except (ValueError, TypeError):
                    payload = {}
                result["risk_full_report"] = payload
                if not result.get("risk_debate_state"):
                    result["risk_debate_state"] = payload
        if debate_state:
            result["investment_debate_state"] = debate_state
        return result

    async def _persist_events(self, job_id: str, final_state: dict) -> None:
        """Persist streaming events including per-agent progress."""
        events = []
        timestamp = utc_now().isoformat()
        total_agents = len(AGENT_NAMES)
        completed_count = 0

        for field, agent_name in AGENT_NAMES.items():
            content = final_state.get(field, "")
            if content:
                completed_count += 1
                progress = completed_count / total_agents if total_agents > 0 else 1.0
                events.append({
                    "analysis_id": job_id,
                    "agent": agent_name,
                    "status": "completed",
                    "message": str(content)[:1000],
                    "progress": progress,
                    "timestamp": timestamp,
                })

        if events:
            try:
                await self.event_repo.insert_batch(events)
            except Exception as exc:
                logger.error("[%s] Failed to persist events: %s", job_id, exc)

    async def _persist_debate(self, job_id: str, final_state: dict) -> None:
        """Persist investment debate results."""
        debate_state = final_state.get("investment_debate_state")
        if debate_state:
            try:
                await self.event_repo.insert({
                    "analysis_id": job_id,
                    "agent": "bull",
                    "status": "completed",
                    "message": f"Bull history: {len(debate_state.get('bull_history', []))} rounds | Bear history: {len(debate_state.get('bear_history', []))} rounds | Judge: {debate_state.get('judge_decision', '')}",
                    "progress": 1.0,
                    "timestamp": utc_now().isoformat(),
                })
            except Exception as exc:
                logger.error("[%s] Failed to persist debate: %s", job_id, exc)

    async def _persist_risk_assessment(
        self, job_id: str, final_state: dict
    ) -> None:
        """Persist risk assessment results."""
        risk_state = final_state.get("risk_debate_state")
        if risk_state:
            try:
                await self.event_repo.insert({
                    "analysis_id": job_id,
                    "agent": "risk",
                    "status": "completed",
                    "message": f"Risk assessment - Aggressive: {len(risk_state.get('aggressive_history', []))} rounds | Conservative: {len(risk_state.get('conservative_history', []))} rounds | Neutral: {len(risk_state.get('neutral_history', []))} rounds | Final: {risk_state.get('judge_decision', '')}",
                    "progress": 1.0,
                    "timestamp": utc_now().isoformat(),
                })
            except Exception as exc:
                logger.error("[%s] Failed to persist risk assessment: %s", job_id, exc)

    async def _persist_trader_decision(
        self, job_id: str, final_state: dict
    ) -> None:
        """Persist trader decision."""
        trader_plan = final_state.get("trader_investment_plan")
        if trader_plan:
            try:
                await self.event_repo.insert({
                    "analysis_id": job_id,
                    "agent": "trader",
                    "status": "completed",
                    "message": f"Trader plan: {str(trader_plan)[:500]}",
                    "progress": 1.0,
                    "timestamp": utc_now().isoformat(),
                })
            except Exception as exc:
                logger.error("[%s] Failed to persist trader decision: %s", job_id, exc)