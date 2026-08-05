from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    market: Optional[str] = Field(default="US", description="Market region e.g. US, India, Crypto, Forex")
    investment_horizon: Optional[str] = Field(default="Swing", description="Horizon e.g. Intraday, Swing, Long Term")
    research_depth: Optional[str] = Field(default="shallow", description="Depth e.g. shallow, medium, deep")
    analysis_date: Optional[str] = Field(default=None, description="Trade date in YYYY-MM-DD format; defaults to today")
    quick_think_llm: Optional[str] = Field(default=None, description="Thinking Agent LLM")
    deep_think_llm: Optional[str] = Field(default=None, description="Deep Thinking Agent LLM")
    models: Optional[dict[str, str]] = Field(
        default=None,
        description="Per-agent model selection, e.g. {'technical': 'Gemini', 'news': 'GLM'}"
    )
    model_selection: Optional[dict[str, str]] = Field(
        default=None,
        description="Alias for per-agent model selection"
    )
    selected_analysts: Optional[list[str]] = Field(
        default=None,
        description="List of analyst types to include",
    )
    max_debate_rounds: Optional[int] = Field(
        default=1, ge=1, le=10, description="Maximum debate rounds for investment debate"
    )
    max_risk_discuss_rounds: Optional[int] = Field(
        default=1, ge=1, le=10, description="Maximum risk discussion rounds"
    )
    notes: Optional[str] = Field(default=None, description="Optional user notes")


class AnalysisResponse(BaseModel):
    job_id: str
    status: str = "pending"


class AnalysisDetail(BaseModel):
    job_id: str
    user_id: Optional[str] = "dev-user"
    ticker: str
    company_name: Optional[str] = None
    market: Optional[str] = "US"
    analysis_date: Optional[str] = None
    investment_horizon: Optional[str] = "Swing"
    notes: Optional[str] = None
    status: str
    selected_models: Optional[dict] = None
    model_selection: Optional[dict] = None
    selected_analysts: Optional[list[str]] = None
    max_debate_rounds: Optional[int] = None
    max_risk_discuss_rounds: Optional[int] = None
    final_trade_decision: Optional[str] = None
    investment_plan: Optional[Union[str, dict]] = None
    market_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    news_report: Optional[str] = None
    fundamentals_report: Optional[str] = None
    trader_investment_plan: Optional[Union[str, dict]] = None
    agent_outputs: Optional[dict] = None
    debate: Optional[dict] = None
    trader: Optional[dict] = None
    risk_manager: Optional[dict] = None
    verdict: Optional[dict] = None
    decision: Optional[str] = None
    confidence: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    models_used: Optional[list[str]] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


class HistoryResponse(BaseModel):
    items: list[AnalysisDetail]
    total: int
    page: int
    page_size: int
    pages: int


class ModelsResponse(BaseModel):
    models: Optional[list[dict]] = None

    class Config:
        extra = "allow"



class ModelsRequest(BaseModel):
    models: dict[str, str] = Field(..., description="Per-agent model selection")