"use client";

/**
 * Custom hook for managing TradingAgents analysis stream via SSE.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
  AnalysisState,
  AnalystReport,
  DebateRound,
  TraderDecision,
  RiskAssessment,
  FinalVerdict,
  SSEEvent,
} from "@/lib/types/analysis";

const initialState: AnalysisState = {
  ticker: "",
  date: "",
  analysts: [
    { agent: "market", status: "pending" },
    { agent: "sentiment", status: "pending" },
    { agent: "news", status: "pending" },
    { agent: "fundamentals", status: "pending" },
  ],
  debate: [],
  status: "idle",
  logs: [],
};

interface UseAnalysisStreamReturn {
  state: AnalysisState;
  startAnalysis: (ticker: string, date: string) => void;
  reset: () => void;
  abort: () => void;
}

export function useAnalysisStream(): UseAnalysisStreamReturn {
  const [state, setState] = useState<AnalysisState>(initialState);
  const abortControllerRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState((prev) => ({ ...prev, status: "idle" }));
  }, []);

  const reset = useCallback(() => {
    abort();
    setState(initialState);
  }, [abort]);

  const startAnalysis = useCallback(
    (ticker: string, date: string) => {
      abort();

      setState({
        ...initialState,
        ticker,
        date,
        status: "connecting",
      });

      abortControllerRef.current = new AbortController();

      fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ticker, date }),
        signal: abortControllerRef.current.signal,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const reader = response.body?.getReader();
          if (!reader) {
            throw new Error("No response body");
          }

          setState((prev) => ({ ...prev, status: "streaming" }));

          const streamReader = reader;
          const decoder = new TextDecoder();
          let buffer = "";

          function readStream(): Promise<void> {
            return streamReader.read().then(({ done, value }) => {
              if (done) {
                return;
              }

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split("\n");
              buffer = lines.pop() || "";

              for (const line of lines) {
                if (line.trim()) {
                  processSSELine(line);
                }
              }

              return readStream();
            });
          }

          return readStream();
        })
        .catch((error) => {
          if (error.name === "AbortError") {
            return;
          }
          setState((prev) => ({
            ...prev,
            status: "error",
            error: error.message,
          }));
        });
    },
    [abort]
  );

  function processSSELine(line: string) {
    if (line.startsWith("event: ")) {
      return;
    }

    if (line.startsWith("data: ")) {
      try {
        const data = JSON.parse(line.slice(6));
        handleEvent(data);
      } catch {
        // Ignore parse errors
      }
    }
  }

  function handleEvent(event: SSEEvent) {
    setState((prev) => {
      const newState = { ...prev };

      switch (event.event) {
        case "analysis_start":
          newState.status = "streaming";
          newState.logs = [...prev.logs, `Analysis started for ${event.ticker}`];
          break;

        case "analysts_initialized":
          newState.logs = [...prev.logs, `Analysts initialized`];
          break;

        case "analyst_start":
          newState.analysts = prev.analysts.map((a) =>
            a.agent === event.agent ? { ...a, status: "running" } : a
          );
          newState.currentAgent = event.agent as string;
          break;

        case "analyst_progress":
          newState.logs = [...prev.logs, `${event.agent}: ${event.message}`];
          break;

        case "analyst_complete": {
          const agentType = event.agent as AnalystReport["agent"];
          newState.analysts = prev.analysts.map((a) =>
            a.agent === agentType
              ? {
                  ...a,
                  status: "complete",
                  report: event.report as string,
                  highlights: event.highlights as string[],
                }
              : a
          );
          newState.logs = [...prev.logs, `${event.agent} analysis complete`];
          break;
        }

        case "debate_start":
          newState.logs = [...prev.logs, "Researcher debate started"];
          break;

        case "debate_progress":
          if (event.bull_argument || event.bear_argument) {
            const newRound: DebateRound = {
              round: (event.round as number) || prev.debate.length + 1,
              bullArgument: (event.bull_argument as string) || "",
              bearArgument: (event.bear_argument as string) || "",
            };
            newState.debate = [...prev.debate, newRound];
          }
          break;

        case "debate_complete":
          newState.logs = [...prev.logs, "Researcher debate complete"];
          break;

        case "trader_decision":
          newState.logs = [...prev.logs, "Trader decision received"];
          if (event.decision) {
            newState.traderDecision = {
              decision: (event.decision as TraderDecision["decision"]) || "HOLD",
              confidence: (event.confidence as number) || 0,
              positionSize: (event.position_size as string) || "0%",
              entryPrice: event.entry_price as number | undefined,
              stopLoss: event.stop_loss as number | undefined,
              targetPrice: event.target_price as number | undefined,
              reasoning: (event.reasoning as string) || "",
            };
          }
          break;

        case "risk_assessment":
          newState.logs = [...prev.logs, "Risk assessment received"];
          if (event.risk) {
            newState.riskAssessment = {
              level: (event.level as RiskAssessment["level"]) || "MEDIUM",
              verdict: (event.verdict as RiskAssessment["verdict"]) || "CONDITIONAL",
              keyRisks: (event.key_risks as string[]) || [],
              mitigation: (event.mitigation as string) || "",
            };
          }
          break;

        case "final_verdict":
          newState.logs = [...prev.logs, "Final verdict received"];
          newState.status = "complete";
          if (event.verdict || event.decision) {
            newState.finalVerdict = {
              decision: (event.decision as FinalVerdict["decision"]) || "HOLD",
              ticker: (event.ticker as string) || prev.ticker,
              date: (event.date as string) || prev.date,
              summary: (event.summary as string) || "",
              positionSize: (event.position_size as string) || "0%",
              entryPrice: event.entry_price as number | undefined,
              stopLoss: event.stop_loss as number | undefined,
              targetPrice: event.target_price as number | undefined,
              riskLevel: (event.risk_level as string) || "",
              timeHorizon: (event.time_horizon as string) || "",
            };
          }
          break;

        case "complete":
          newState.status = "complete";
          newState.logs = [...prev.logs, "Analysis complete"];
          break;

        case "error":
          newState.status = "error";
          newState.error = (event.message as string) || "Unknown error";
          newState.logs = [...prev.logs, `Error: ${event.message}`];
          break;

        case "log":
          if (event.message) {
            newState.logs = [...prev.logs, event.message as string];
          }
          break;
      }

      return newState;
    });
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abort();
    };
  }, [abort]);

  return { state, startAnalysis, reset, abort };
}
