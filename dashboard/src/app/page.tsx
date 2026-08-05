"use client";

/**
 * TradingAgents Dashboard Main Page
 * 
 * Dark terminal-style interface for running multi-agent trading analysis.
 */

import { useState } from "react";
import { AnalysisForm } from "@/components/analysis-form";
import { TerminalHeader } from "@/components/terminal/terminal-header";
import { AnalystPanel } from "@/components/agent-panels/analyst-panel";
import { DebatePanel } from "@/components/agent-panels/debate-panel";
import { TraderPanel } from "@/components/agent-panels/trader-panel";
import { RiskPanel } from "@/components/agent-panels/risk-panel";
import { FinalVerdict } from "@/components/agent-panels/final-verdict";
import { useAnalysisStream } from "@/hooks/use-analysis-stream";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export default function Dashboard() {
  const { state, startAnalysis, reset, abort } = useAnalysisStream();
  const [showLogs, setShowLogs] = useState(false);

  const isLoading = state.status === "connecting" || state.status === "streaming";
  const hasResults = state.status === "complete" || state.analysts.some(a => a.status === "complete");

  return (
    <div className="min-h-screen bg-terminal flex flex-col">
      {/* Terminal Header */}
      <TerminalHeader 
        status={state.status}
        onAbort={abort}
        showAbort={isLoading}
      />

      {/* Main Content */}
      <main className="flex-1 container mx-auto px-4 py-6 max-w-7xl">
        {/* Analysis Form */}
        <div className="mb-8">
          <AnalysisForm
            onSubmit={startAnalysis}
            onReset={reset}
            isLoading={isLoading}
          />
        </div>

        <Separator className="bg-zinc-800 my-6" />

        {/* Results Area */}
        {hasResults && (
          <ScrollArea className="h-[calc(100vh-400px)] scrollbar-terminal">
            <div className="space-y-6 pb-20">
              {/* Analyst Reports */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {state.analysts.map((analyst) => (
                  <AnalystPanel
                    key={analyst.agent}
                    report={analyst}
                  />
                ))}
              </div>

              {/* Researcher Debate */}
              {state.debate.length > 0 && (
                <DebatePanel rounds={state.debate} />
              )}

              {/* Trader Decision */}
              {state.traderDecision && (
                <TraderPanel decision={state.traderDecision} />
              )}

              {/* Risk Assessment */}
              {state.riskAssessment && (
                <RiskPanel assessment={state.riskAssessment} />
              )}

              {/* Final Verdict */}
              {state.finalVerdict && (
                <FinalVerdict verdict={state.finalVerdict} />
              )}
            </div>
          </ScrollArea>
        )}

        {/* Error Display */}
        {state.status === "error" && state.error && (
          <div className="mt-6 p-4 border border-red-500/50 bg-red-500/10 rounded-lg">
            <h3 className="text-red-400 font-mono font-bold mb-2">Error</h3>
            <p className="text-red-300 font-mono text-sm">{state.error}</p>
          </div>
        )}

        {/* Logs Toggle */}
        {state.logs.length > 0 && (
          <div className="mt-6">
            <button
              onClick={() => setShowLogs(!showLogs)}
              className="text-zinc-500 hover:text-zinc-300 text-xs font-mono uppercase tracking-wider"
            >
              {showLogs ? "Hide Logs" : "Show Logs"} ({state.logs.length})
            </button>
            
            {showLogs && (
              <div className="mt-2 p-3 bg-terminal-light rounded border border-zinc-800 max-h-48 overflow-y-auto scrollbar-terminal">
                <pre className="text-xs font-mono text-zinc-400">
                  {state.logs.map((log, i) => (
                    <div key={i} className="py-0.5">
                      <span className="text-zinc-600">[{i + 1}]</span> {log}
                    </div>
                  ))}
                </pre>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 py-4 px-4">
        <div className="container mx-auto max-w-7xl flex justify-between items-center">
          <p className="text-zinc-600 text-xs font-mono">
            TradingAgents Dashboard v1.0
          </p>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                state.status === "streaming"
                  ? "bg-emerald-500 animate-pulse"
                  : state.status === "error"
                  ? "bg-red-500"
                  : state.status === "complete"
                  ? "bg-blue-500"
                  : "bg-zinc-600"
              }`}
            />
            <span className="text-zinc-500 text-xs font-mono uppercase">
              {state.status}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
