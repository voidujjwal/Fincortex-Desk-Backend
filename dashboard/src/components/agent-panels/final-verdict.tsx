"use client";

import { FinalVerdict } from "@/lib/types/analysis";
import { formatCurrency, getDecisionColor, getDecisionBgColor } from "@/lib/utils";
import { Award, Zap, Calendar, Target, Shield, Clock, CheckCircle } from "lucide-react";

interface FinalVerdictProps {
  verdict?: FinalVerdict;
}

export function FinalVerdictCard({ verdict }: FinalVerdictProps) {
  if (!verdict) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-6 text-center shadow-lg">
        <div className="flex justify-center mb-3">
          <Award className="h-8 w-8 text-zinc-600 animate-pulse" />
        </div>
        <h3 className="font-mono text-sm font-bold text-zinc-400 uppercase tracking-wider">
          FINAL PORTFOLIO VERDICT PENDING
        </h3>
        <p className="font-mono text-xs text-zinc-600 mt-1">
          Complete pipeline execution to view Portfolio Manager&apos;s synthesized investment rating.
        </p>
      </div>
    );
  }

  const decisionColor = getDecisionColor(verdict.decision);
  const decisionBg = getDecisionBgColor(verdict.decision);

  return (
    <div className="rounded-xl border border-emerald-500/40 bg-zinc-950 p-6 shadow-[0_0_30px_rgba(16,185,129,0.12)] relative overflow-hidden space-y-5">
      {/* Top Banner & Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <Award className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-mono text-base font-bold text-zinc-100 uppercase tracking-wider">
                PORTFOLIO MANAGER FINAL VERDICT
              </h2>
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
            </div>
            <p className="font-mono text-xs text-zinc-400 flex items-center gap-2 mt-0.5">
              <span>TICKER: <strong className="text-zinc-200">{verdict.ticker}</strong></span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3 text-zinc-500" />
                {verdict.date}
              </span>
            </p>
          </div>
        </div>

        {/* Big Decision Badge */}
        <div className={`px-5 py-2.5 rounded-lg border text-center font-mono ${decisionBg}`}>
          <div className="text-[10px] text-zinc-400 uppercase tracking-widest font-semibold">
            RECOMMENDED RATING
          </div>
          <div className={`text-2xl font-black ${decisionColor}`}>
            [█] {verdict.decision}
          </div>
        </div>
      </div>

      {/* Key Recommendation Parameters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1">
            <Zap className="h-3.5 w-3.5 text-blue-400" />
            POSITION SIZE
          </div>
          <div className="text-base font-bold font-mono text-zinc-100 mt-1">
            {verdict.positionSize}
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1">
            <Target className="h-3.5 w-3.5 text-emerald-400" />
            ENTRY TARGET
          </div>
          <div className="text-base font-bold font-mono text-emerald-400 mt-1">
            {formatCurrency(verdict.entryPrice)}
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1">
            <Shield className="h-3.5 w-3.5 text-orange-400" />
            RISK LEVEL
          </div>
          <div className="text-base font-bold font-mono text-orange-400 mt-1">
            {verdict.riskLevel || "MEDIUM"}
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="text-[11px] font-mono text-zinc-500 uppercase flex items-center gap-1">
            <Clock className="h-3.5 w-3.5 text-purple-400" />
            HORIZON
          </div>
          <div className="text-base font-bold font-mono text-purple-300 mt-1">
            {verdict.timeHorizon || "3-6 MONTHS"}
          </div>
        </div>
      </div>

      {/* Executive Summary */}
      {verdict.summary && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 space-y-2">
          <div className="font-mono text-xs text-zinc-300 font-bold uppercase flex items-center gap-1.5">
            <CheckCircle className="h-4 w-4 text-emerald-400" />
            EXECUTIVE SUMMARY & THESIS
          </div>
          <p className="font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">
            {verdict.summary}
          </p>
        </div>
      )}
    </div>
  );
}
