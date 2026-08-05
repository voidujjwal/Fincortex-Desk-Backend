"use client";

/**
 * Terminal Header Component
 * 
 * Displays the terminal-style header with window controls and status.
 */

import { X, Minus, Square, Terminal, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

interface TerminalHeaderProps {
  status: "idle" | "connecting" | "streaming" | "complete" | "error";
  onAbort: () => void;
  showAbort: boolean;
}

export function TerminalHeader({
  status,
  onAbort,
  showAbort,
}: TerminalHeaderProps) {
  const getStatusColor = () => {
    switch (status) {
      case "streaming":
        return "text-emerald-400";
      case "error":
        return "text-red-400";
      case "complete":
        return "text-blue-400";
      case "connecting":
        return "text-amber-400";
      default:
        return "text-zinc-500";
    }
  };

  const getStatusText = () => {
    switch (status) {
      case "streaming":
        return "● ANALYZING";
      case "error":
        return "● ERROR";
      case "complete":
        return "● COMPLETE";
      case "connecting":
        return "● CONNECTING";
      default:
        return "○ IDLE";
    }
  };

  return (
    <header className="bg-zinc-900/80 backdrop-blur-md border-b border-zinc-800">
      {/* Title Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-950/50">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80 hover:bg-red-400 transition-colors" />
            <div className="w-3 h-3 rounded-full bg-amber-500/80 hover:bg-amber-400 transition-colors" />
            <div className="w-3 h-3 rounded-full bg-emerald-500/80 hover:bg-emerald-400 transition-colors" />
          </div>
          <span className="ml-3 text-zinc-500 text-xs font-mono">
            trading-agents — -zsh — 80x24
          </span>
        </div>

        {showAbort && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onAbort}
            className="h-6 text-xs font-mono text-red-400 hover:text-red-300 hover:bg-red-500/10"
          >
            ABORT
          </Button>
        )}
      </div>

      {/* App Header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500/20 to-blue-500/20 border border-emerald-500/30 flex items-center justify-center">
            <Terminal className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white font-mono tracking-tight">
              TradingAgents
            </h1>
            <p className="text-xs text-zinc-500 font-mono">
              Multi-Agent Trading Analysis Framework
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Activity className={`w-4 h-4 ${getStatusColor()} animate-pulse`} />
            <span className={`text-xs font-mono font-bold ${getStatusColor()}`}>
              {getStatusText()}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
