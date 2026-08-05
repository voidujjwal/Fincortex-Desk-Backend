"use client";

/**
 * Trader Panel Component
 * 
 * Displays the trader's buy/sell/hold decision with confidence and reasoning.
 */

import { TraderDecision } from "@/lib/types/analysis";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Briefcase, Target, Shield, TrendingUp } from "lucide-react";
import { formatCurrency, formatPercentage } from "@/lib/utils";

interface TraderPanelProps {
  decision: TraderDecision;
}

export function TraderPanel({ decision }: TraderPanelProps) {
  const getDecisionColor = () => {
    switch (decision.decision) {
      case "BUY":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/50";
      case "SELL":
        return "bg-red-500/20 text-red-400 border-red-500/50";
      case "HOLD":
      default:
        return "bg-amber-500/20 text-amber-400 border-amber-500/50";
    }
  };

  const getConfidenceColor = () => {
    if (decision.confidence >= 80) return "text-emerald-400";
    if (decision.confidence >= 60) return "text-amber-400";
    return "text-red-400";
  };

  return (
    <Card className="border-blue-500/30 bg-blue-500/5 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-mono text-blue-400 flex items-center gap-2">
          <Briefcase className="w-4 h-4" />
          TRADER DECISION
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Main Decision */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className={`text-lg font-bold font-mono px-4 py-1 ${getDecisionColor()}`}
            >
              {decision.decision}
            </Badge>
            <div className="text-sm font-mono">
              <span className="text-zinc-500">Confidence:</span>
              <span className={`ml-2 font-bold ${getConfidenceColor()}`}>
                {decision.confidence}%
              </span>
            </div>
          </div>
        </div>

        {/* Position Sizing */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-terminal-light rounded p-2 border border-zinc-800">
            <div className="text-xs text-zinc-500 font-mono mb-1">Position Size</div>
            <div className="text-sm font-mono text-blue-400 font-bold">
              {decision.positionSize}
            </div>
          </div>
          
          {decision.entryPrice && (
            <div className="bg-terminal-light rounded p-2 border border-zinc-800">
              <div className="text-xs text-zinc-500 font-mono mb-1">Entry</div>
              <div className="text-sm font-mono text-emerald-400 font-bold">
                {formatCurrency(decision.entryPrice)}
              </div>
            </div>
          )}
          
          {decision.stopLoss && (
            <div className="bg-terminal-light rounded p-2 border border-zinc-800">
              <div className="text-xs text-zinc-500 font-mono mb-1">Stop Loss</div>
              <div className="text-sm font-mono text-red-400 font-bold">
                {formatCurrency(decision.stopLoss)}
              </div>
            </div>
          )}
          
          {decision.targetPrice && (
            <div className="bg-terminal-light rounded p-2 border border-zinc-800">
              <div className="text-xs text-zinc-500 font-mono mb-1">Target</div>
              <div className="text-sm font-mono text-emerald-400 font-bold">
                {formatCurrency(decision.targetPrice)}
              </div>
            </div>
          )}
        </div>

        {/* Reasoning */}
        {decision.reasoning && (
          <div className="bg-terminal-light rounded p-3 border border-zinc-800">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-zinc-500" />
              <span className="text-xs text-zinc-500 font-mono uppercase">Reasoning</span>
            </div>
            <p className="text-sm font-mono text-zinc-300 leading-relaxed">
              {decision.reasoning}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
