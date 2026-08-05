"use client";

import { useEffect, useRef } from "react";
import { Terminal, Copy, Check } from "lucide-react";
import { useState } from "react";

interface TerminalStreamProps {
  logs: string[];
  status: "idle" | "connecting" | "streaming" | "complete" | "error";
  error?: string;
}

export function TerminalStream({ logs, status, error }: TerminalStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, error]);

  const copyLogs = () => {
    if (logs.length > 0) {
      navigator.clipboard.writeText(logs.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 font-mono text-xs shadow-inner flex flex-col h-[320px]">
      {/* Console bar */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/60 px-3 py-2 text-zinc-400 select-none">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-emerald-400" />
          <span className="font-semibold text-zinc-300">LIVE_LOG_STREAM</span>
          <span className="text-zinc-600">({logs.length} events)</span>
        </div>

        <button
          onClick={copyLogs}
          disabled={logs.length === 0}
          className="flex items-center gap-1 hover:text-zinc-200 disabled:opacity-40 transition-colors text-[11px]"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400">COPIED</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>COPY LOGS</span>
            </>
          )}
        </button>
      </div>

      {/* Log Output Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-1.5 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent"
      >
        {logs.length === 0 && status === "idle" && (
          <div className="text-zinc-600 italic py-8 text-center">
            System ready. Enter ticker and date above to initiate multi-agent trading analysis.
          </div>
        )}

        {logs.map((log, index) => {
          let colorClass = "text-zinc-300";
          if (log.toLowerCase().includes("error")) colorClass = "text-red-400";
          else if (log.toLowerCase().includes("complete") || log.toLowerCase().includes("initialized"))
            colorClass = "text-emerald-400";
          else if (log.toLowerCase().includes("market")) colorClass = "text-amber-400";
          else if (log.toLowerCase().includes("sentiment")) colorClass = "text-cyan-400";
          else if (log.toLowerCase().includes("news")) colorClass = "text-purple-400";
          else if (log.toLowerCase().includes("trader") || log.toLowerCase().includes("decision"))
            colorClass = "text-blue-400";

          return (
            <div key={index} className="flex items-start gap-2 leading-relaxed">
              <span className="text-zinc-600 select-none">[{index + 1}]</span>
              <span className="text-emerald-500/70 select-none">&gt;</span>
              <span className={colorClass}>{log}</span>
            </div>
          );
        })}

        {status === "streaming" && (
          <div className="flex items-center gap-2 text-emerald-400/80 animate-pulse pt-1">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
            <span>Processing agent state updates...</span>
          </div>
        )}

        {error && (
          <div className="rounded border border-red-500/30 bg-red-950/30 p-2.5 text-red-400 font-medium my-2">
            [FATAL ERROR]: {error}
          </div>
        )}
      </div>
    </div>
  );
}
