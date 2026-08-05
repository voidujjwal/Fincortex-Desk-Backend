#!/usr/bin/env python3
"""
TradingAgents Runner - Python wrapper for streaming analysis output.

This script interfaces with the TradingAgents framework and streams
JSON events to stdout for consumption by the Next.js API.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent directory to path to import TradingAgents
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Import TradingAgents components
try:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
except ImportError as e:
    print(json.dumps({
        "event": "error",
        "type": "import_error",
        "message": f"Failed to import TradingAgents: {str(e)}"
    }), flush=True)
    sys.exit(1)


class JSONStreamHandler(logging.Handler):
    """Custom logging handler that emits JSON to stdout."""
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record as JSON."""
        log_entry = {
            "event": "log",
            "level": record.levelname,
            "message": self.format(record),
            "timestamp": datetime.utcnow().isoformat()
        }
        print(json.dumps(log_entry), flush=True)


def emit_event(event_type: str, data: Dict[str, Any]) -> None:
    """Emit an event as JSON to stdout."""
    event = {
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        **data
    }
    print(json.dumps(event), flush=True)


def run_analysis(ticker: str, date: str) -> None:
    """Run TradingAgents analysis and stream events."""
    
    emit_event("analysis_start", {
        "ticker": ticker,
        "date": date
    })
    
    try:
        # Initialize TradingAgents with custom config
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = "openai"  # Default provider
        
        ta = TradingAgentsGraph(
            selected_analysts=["market", "social", "news", "fundamentals"],
            debug=True,
            config=config
        )
        
        emit_event("analysts_initialized", {
            "analysts": ["market", "social", "news", "fundamentals"]
        })
        
        # Run the analysis
        final_state, decision = ta.propagate(ticker, date)
        
        # Extract and emit analyst reports
        if final_state.get("market_report"):
            emit_event("analyst_complete", {
                "agent": "market",
                "report": final_state["market_report"]
            })
        
        if final_state.get("sentiment_report"):
            emit_event("analyst_complete", {
                "agent": "sentiment",
                "report": final_state["sentiment_report"]
            })
        
        if final_state.get("news_report"):
            emit_event("analyst_complete", {
                "agent": "news",
                "report": final_state["news_report"]
            })
        
        if final_state.get("fundamentals_report"):
            emit_event("analyst_complete", {
                "agent": "fundamentals",
                "report": final_state["fundamentals_report"]
            })
        
        # Emit researcher debate
        if final_state.get("investment_debate_state"):
            emit_event("debate_complete", {
                "debate": final_state["investment_debate_state"]
            })
        
        # Emit trader decision
        if final_state.get("trader_investment_plan"):
            emit_event("trader_decision", {
                "decision": final_state["trader_investment_plan"]
            })
        
        # Emit risk assessment
        if final_state.get("risk_debate_state"):
            emit_event("risk_assessment", {
                "risk": final_state["risk_debate_state"]
            })
        
        # Emit final verdict
        if final_state.get("final_trade_decision"):
            emit_event("final_verdict", {
                "verdict": final_state["final_trade_decision"],
                "decision": decision
            })
        
        # Emit complete event
        emit_event("complete", {
            "ticker": ticker,
            "date": date,
            "status": "success"
        })
        
    except Exception as e:
        emit_event("error", {
            "type": "analysis_error",
            "message": str(e),
            "traceback": str(sys.exc_info()[2])
        })
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 3:
        print(json.dumps({
            "event": "error",
            "type": "usage_error",
            "message": "Usage: python trading_agents_runner.py <ticker> <date>"
        }), flush=True)
        sys.exit(1)
    
    ticker = sys.argv[1].upper()
    date = sys.argv[2]
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        print(json.dumps({
            "event": "error",
            "type": "validation_error",
            "message": "Date must be in YYYY-MM-DD format"
        }), flush=True)
        sys.exit(1)
    
    run_analysis(ticker, date)


if __name__ == "__main__":
    main()
