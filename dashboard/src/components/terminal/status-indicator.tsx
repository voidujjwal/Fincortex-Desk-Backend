"use client";

import { AnalysisState } from "@/lib/types/analysis";
import { cn } from "@/lib/utils";

interface StatusIndicatorProps {
  status: AnalysisState["status"];
  currentAgent?: string;
  className?: string;
}

export function StatusIndicator({
  status,
  currentAgent,
  className,
}: StatusIndicatorProps) {
  const getStatusConfig = () => {
    switch (status) {
      case "idle":
        return {
          label: "SYSTEM READY",
          dotClass: "bg-zinc-500",
          textClass: "text-zinc-400",
          borderClass: "border-zinc-800 bg-zinc-900/50",
          ping: false,
        };
      case "connecting":
        return {
          label: "CONNECTING...",
          dotClass: "bg-amber-400",
          textClass: "text-amber-400",
          borderClass: "border-amber-500/30 bg-amber-950/20",
          ping: true,
        };
      case "streaming":
        return {
          label: currentAgent
            ? `RUNNING: ${currentAgent.toUpperCase()}`
            : "ANALYSIS IN PROGRESS",
          dotClass: "bg-emerald-400",
          textClass: "text-emerald-400",
          borderClass: "border-emerald-500/30 bg-emerald-950/20",
          ping: true,
        };
      case "complete":
        return {
          label: "ANALYSIS COMPLETE",
          dotClass: "bg-cyan-400",
          textClass: "text-cyan-400",
          borderClass: "border-cyan-500/30 bg-cyan-950/20",
          ping: false,
        };
      case "error":
        return {
          label: "SYSTEM ERROR",
          dotClass: "bg-red-500",
          textClass: "text-red-400",
          borderClass: "border-red-500/30 bg-red-950/20",
          ping: false,
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2.5 rounded-full border px-3 py-1 text-xs font-mono font-medium transition-all shadow-sm select-none",
        config.borderClass,
        className
      )}
    >
      <span className="relative flex h-2 w-2">
        {config.ping && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              config.dotClass
            )}
          />
        )}
        <span
          className={cn("relative inline-flex h-2 w-2 rounded-full", config.dotClass)}
        />
      </span>
      <span className={cn("tracking-wider font-semibold", config.textClass)}>
        {config.label}
      </span>
    </div>
  );
}
