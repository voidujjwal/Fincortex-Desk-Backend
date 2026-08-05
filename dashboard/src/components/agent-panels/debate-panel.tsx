"use client";

/**
 * Debate Panel Component
 * 
 * Displays bull vs bear researcher arguments side by side.
 */

import { DebateRound } from "@/lib/types/analysis";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Swords } from "lucide-react";

interface DebatePanelProps {
  rounds: DebateRound[];
}

export function DebatePanel({ rounds }: DebatePanelProps) {
  const latestRound = rounds[rounds.length - 1];

  return (
    <Card className="border-zinc-700 bg-card/50 backdrop-blur-sm overflow-hidden">
      <CardHeader className="pb-3 border-b border-zinc-800">
        <CardTitle className="text-sm font-mono text-zinc-300 flex items-center gap-2">
          <Swords className="w-4 h-4 text-zinc-500" />
          RESEARCHER DEBATE
          <span className="text-xs text-zinc-600 ml-2">
            Round {latestRound?.round || 1} of {rounds.length}
          </span>
        </CardTitle>
      </CardHeader>

      <CardContent className="p-0">
        <div className="grid grid-cols-1 md:grid-cols-2">
          {/* Bull Case */}
          <div className="border-r border-zinc-800 p-4 bg-emerald-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </div>
              <h3 className="text-sm font-mono font-bold text-emerald-400">
                BULL CASE
              </h3>
            </div>
            <div className="text-sm font-mono text-zinc-300 leading-relaxed whitespace-pre-wrap">
              {latestRound?.bullArgument || "No bull argument available"}
            </div>
          </div>

          {/* Bear Case */}
          <div className="p-4 bg-red-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-red-500/20 border border-red-500/30 flex items-center justify-center">
                <TrendingDown className="w-4 h-4 text-red-400" />
              </div>
              <h3 className="text-sm font-mono font-bold text-red-400">
                BEAR CASE
              </h3>
            </div>
            <div className="text-sm font-mono text-zinc-300 leading-relaxed whitespace-pre-wrap">
              {latestRound?.bearArgument || "No bear argument available"}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
