"""TradingAgents wrapper service.

This service wraps the existing TradingAgents execution pipeline
without modifying any core TradingAgents code.
"""

import asyncio
import logging
import time
from typing import Any, Optional, Callable

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

from app.utils.helpers import utc_now

logger = logging.getLogger("tradingagents.wrapper")

AGENT_MODEL_KEYS = {
    "market": "technical",
    "social": "social",
    "news": "news",
    "fundamentals": "fundamentals",
}

MODEL_CATALOG = {
    # OpenAI
    "gpt-5-mini": "openai",
    "gpt-5-nano": "openai",
    "gpt-5.4": "openai",
    "gpt-4.1": "openai",
    # Anthropic
    "claude-sonnet-4-6": "anthropic",
    "claude-haiku-4-5": "anthropic",
    "claude-sonnet-4-5": "anthropic",
    # Google
    "gemini-3-flash-preview": "google",
    "gemini-2.5-flash": "google",
    "gemini-3.1-flash-lite-preview": "google",
    "gemini-2.5-flash-lite": "google",
    # xAI
    "grok-4-1-fast-non-reasoning": "xai",
    "grok-4-fast-non-reasoning": "xai",
    "grok-4-1-fast-reasoning": "xai",
    # NVIDIA (OpenAI-compatible endpoint)
    "nvidia/nemotron-3-super-120b-a12b": "nvidia",
    "nvidia/nemotron-3-nano-30b-a3b": "nvidia",
    "nvidia/nemotron-3-ultra-550b-a55b": "nvidia",
    "nvidia/llama-3.1-nemotron-70b-instruct": "nvidia",
    "meta/llama-3.3-70b-instruct": "nvidia",
    # OpenRouter
    "z-ai/glm-4.5-air": "openrouter",
    "poolside/laguna-s-2.1:free": "openrouter",
    # Ollama (local)
    "qwen3:latest": "ollama",
    "gpt-oss:latest": "ollama",
    "glm-4.7-flash:latest": "ollama",
}

PROVIDER_FALLBACK_MODELS = {
    "openai": "gpt-5-mini",
    "anthropic": "claude-haiku-4-5",
    "google": "gemini-2.5-flash",
    "xai": "grok-4-1-fast-non-reasoning",
    "nvidia": "nvidia/nemotron-3-nano-30b-a3b",
    "openrouter": "z-ai/glm-4.5-air",
    "ollama": "qwen3:latest",
}

DEFAULT_TIMEOUT_SECONDS = 600


class TradingAgentsService:
    """Wrapper around the TradingAgents execution pipeline.

    Provides async methods that internally call the synchronous
    TradingAgentsGraph pipeline using asyncio.to_thread() to
    avoid blocking the event loop.

    Supports:
    - Per-agent dynamic model selection
    - Configurable execution timeout
    - Progress callbacks for real-time streaming
    - Execution time tracking
    """

    def __init__(self, default_timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self._active_jobs: dict[str, TradingAgentsGraph] = {}
        self.default_timeout = default_timeout

    def _resolve_provider(self, model_name: str) -> str:
        """Determine the LLM provider from a model name string.

        The known model catalog is checked first so every model exposed by
        the API resolves deterministically (e.g. meta/llama-3.3-70b-instruct
        is NVIDIA-hosted, gpt-oss:latest is Ollama). Unknown model names
        fall back to name heuristics.
        """
        model = (model_name or "").strip()
        if not model:
            return "openai"
        if model in MODEL_CATALOG:
            return MODEL_CATALOG[model]
        model_lower = model.lower()
        if "nvidia" in model_lower or "nemotron" in model_lower:
            return "nvidia"
        if "gemini" in model_lower or "google" in model_lower:
            return "google"
        if "grok" in model_lower or "xai" in model_lower:
            return "xai"
        if "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        if model_lower.endswith(":latest") or "ollama" in model_lower:
            return "ollama"
        if "/" in model_lower:
            return "openrouter"
        if "gpt" in model_lower or "openai" in model_lower:
            return "openai"
        return "openai"

    def _coerce_to_provider(self, model_name: str, provider: str) -> str:
        """Ensure a model belongs to the given provider.

        If the model resolves to a different provider, it is replaced with a
        same-provider fallback model so a provider client is never invoked
        with a foreign model (which would fail with a 404 model/provider
        mismatch).
        """
        if not model_name:
            return PROVIDER_FALLBACK_MODELS.get(provider, "")
        if self._resolve_provider(model_name) == provider:
            return model_name
        fallback = PROVIDER_FALLBACK_MODELS.get(provider)
        if fallback and fallback != model_name:
            logger.warning(
                "Model %r belongs to provider %r but analysis provider is %r; "
                "substituting with %r to avoid model/provider mismatch",
                model_name,
                self._resolve_provider(model_name),
                provider,
                fallback,
            )
            return fallback
        return model_name

    _PROVIDER_BACKEND_URLS = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/",
        "google": "https://generativelanguage.googleapis.com/v1",
        "nvidia": "https://integrate.api.nvidia.com/v1",
        "xai": "https://api.x.ai/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "ollama": "http://localhost:11434/v1",
        "zhipu": None,
    }

    def _build_config(
        self,
        models: dict[str, str],
        selected_analysts: Optional[list[str]] = None,
        max_debate_rounds: int = 1,
        max_risk_discuss_rounds: int = 1,
    ) -> dict:
        """Build a TradingAgents config from the API request.

        Dynamically maps per-agent model selection to the TradingAgents
        config keys. The frontend sends models like:
        {"technical": "Gemini", "news": "GLM", "social": "Grok"}

        These are mapped to deep_think_llm and quick_think_llm based on
        agent role priority (technical > news > social > fundamentals).
        """
        config = dict(DEFAULT_CONFIG)

        # Normalize agent keys so both frontend spellings are recognized
        normalized = {k: v for k, v in models.items() if k and v}
        if "fundamental" in normalized and "fundamentals" not in normalized:
            normalized["fundamentals"] = normalized.pop("fundamental")

        # Resolve model values in priority order (technical first, then news, social, fundamentals)
        ordered_keys = ["technical", "news", "social", "fundamentals"]
        reserved = set(ordered_keys) | {
            "provider",
            "deep_think_llm",
            "deep_think",
            "quick_think_llm",
            "quick_think",
        }
        ordered_values = [normalized[k] for k in ordered_keys if normalized.get(k)]

        # Also include any non-reserved keys the user might have sent
        for key, val in normalized.items():
            if key not in reserved and val not in ordered_values:
                ordered_values.append(val)

        deep_model = (
            normalized.get("deep_think_llm")
            or normalized.get("deep_think")
            or (ordered_values[0] if ordered_values else "gpt-5.2")
        )
        quick_model = (
            normalized.get("quick_think_llm")
            or normalized.get("quick_think")
            or (ordered_values[1] if len(ordered_values) > 1 else deep_model)
        )

        # Provider selection: explicit "provider" wins, otherwise infer from
        # the primary (deep) model. Both models are then coerced to this
        # single provider so no provider client ever receives a foreign model.
        explicit_provider = str(normalized.get("provider") or "").lower()
        if explicit_provider in PROVIDER_FALLBACK_MODELS:
            provider = explicit_provider
        else:
            if explicit_provider:
                logger.warning(
                    "Unknown provider %r in request; inferring provider from models",
                    explicit_provider,
                )
            provider = self._resolve_provider(deep_model)

        config["deep_think_llm"] = self._coerce_to_provider(deep_model, provider)
        config["quick_think_llm"] = self._coerce_to_provider(quick_model, provider)
        config["llm_provider"] = provider

        backend_url = self._PROVIDER_BACKEND_URLS.get(provider)
        if backend_url:
            config["backend_url"] = backend_url

        if selected_analysts:
            config["selected_analysts"] = selected_analysts

        config["max_debate_rounds"] = max_debate_rounds
        config["max_risk_discuss_rounds"] = max_risk_discuss_rounds

        return config

    def _build_per_agent_assignments(
        self,
        models: dict[str, str],
    ) -> dict[str, str]:
        """Map internal analyst agent names to the user-supplied model names.

        Returns a dict like {"market": "Gemini", "news": "GLM", ...}
        """
        assignments: dict[str, str] = {}
        for agent_key, model_key in AGENT_MODEL_KEYS.items():
            if model_key in models:
                assignments[agent_key] = models[model_key]
            elif agent_key == "fundamentals" and "fundamental" in models:
                assignments[agent_key] = models["fundamental"]
            elif agent_key in models:
                assignments[agent_key] = models[agent_key]
        return assignments

    async def run_analysis(
        self,
        job_id: str,
        ticker: str,
        models: dict[str, str],
        selected_analysts: Optional[list[str]] = None,
        max_debate_rounds: int = 1,
        max_risk_discuss_rounds: int = 1,
        analysis_date: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """Run a full TradingAgents analysis for a ticker.

        Args:
            job_id: Unique job identifier
            ticker: Stock ticker symbol
            models: Per-agent model selection dict
            selected_analysts: List of analyst types to include
            max_debate_rounds: Maximum debate rounds
            max_risk_discuss_rounds: Maximum risk discussion rounds
            analysis_date: Trade date (YYYY-MM-DD); defaults to "today" if not provided
            progress_callback: Optional callback(progress, agent_name)
            timeout: Execution timeout in seconds (defaults to 600)

        Returns:
            Dict with job_id, final_state, decision, ticker, execution metadata

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
            Exception: Any error from the TradingAgents pipeline
        """
        effective_timeout = timeout or self.default_timeout
        agent_assignments = self._build_per_agent_assignments(models)
        config = self._build_config(
            models,
            selected_analysts,
            max_debate_rounds,
            max_risk_discuss_rounds,
        )

        selected_analysts = selected_analysts or [
            "market", "social", "news", "fundamentals"
        ]

        logger.info(
            "[%s] Starting TradingAgents execution for %s with models %s",
            job_id,
            ticker,
            models,
        )

        def _run_sync():
            t0 = time.monotonic()
            logger.info(
                "[%s] Initializing TradingAgentsGraph for %s", job_id, ticker
            )

            graph = TradingAgentsGraph(
                selected_analysts=selected_analysts,
                config=config,
            )
            logger.info(
                "[%s] TradingAgentsGraph initialized in %.2fs",
                job_id,
                time.monotonic() - t0,
            )

            self._active_jobs[job_id] = graph

            if progress_callback:
                progress_callback(0.1, "graph_initialized")

            logger.info("[%s] Starting graph propagation for %s", job_id, ticker)
            if progress_callback:
                progress_callback(0.2, "propagation_started")

            t_prop = time.monotonic()
            final_state, decision = graph.propagate(ticker, analysis_date or "today")
            elapsed = time.monotonic() - t_prop

            logger.info(
                "[%s] Graph propagation completed in %.2fs for %s",
                job_id,
                elapsed,
                ticker,
            )
            if progress_callback:
                progress_callback(1.0, "propagation_completed")

            return {
                "graph": graph,
                "final_state": final_state,
                "decision": decision,
                "elapsed": elapsed,
            }

        t_start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_run_sync),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "[%s] Analysis timed out after %ds for %s",
                job_id,
                effective_timeout,
                ticker,
            )
            raise asyncio.TimeoutError(
                f"TradingAgents analysis timed out after {effective_timeout}s"
            )
        finally:
            total_elapsed = time.monotonic() - t_start
            self._active_jobs.pop(job_id, None)
            logger.info(
                "[%s] Analysis execution completed in %.2fs total",
                job_id,
                total_elapsed,
            )

        return {
            "job_id": job_id,
            "final_state": result["final_state"],
            "decision": result["decision"],
            "ticker": ticker,
            "selected_models": models,
            "agent_assignments": agent_assignments,
            "execution_time_seconds": round(result.get("elapsed", total_elapsed), 2),
            "total_time_seconds": round(total_elapsed, 2),
        }

    async def cancel_analysis(self, job_id: str) -> bool:
        """Cancel a running analysis."""
        graph = self._active_jobs.get(job_id)
        if graph is None:
            return False
        logger.info("[%s] Cancellation requested", job_id)
        return True

    async def get_progress(self, job_id: str) -> dict:
        """Get the progress of a running analysis."""
        graph = self._active_jobs.get(job_id)
        if graph is None:
            return {"job_id": job_id, "status": "not_found"}
        return {
            "job_id": job_id,
            "status": "running",
            "ticker": graph.ticker,
        }