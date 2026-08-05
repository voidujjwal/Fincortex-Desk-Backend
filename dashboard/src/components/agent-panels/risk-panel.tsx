"use client";

import { RiskAssessment } from "@/lib/types/analysis";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ShieldAlert, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

interface RiskPanelProps {
  riskAssessment?: RiskAssessment;
}

export function RiskPanel({ riskAssessment }: RiskPanelProps) {
  if (!riskAssessment) {
    return (
      <Card className="border-orange-500/30 bg-orange-950/10">
        <CardHeader className="border-orange-500/20 text-orange-400">
          <CardTitle className="text-zinc-100 flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-orange-400" />
            RISK MANAGEMENT EVALUATION
          </CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-zinc-500 text-xs italic">
          Risk management committee is evaluating proposed position...
        </CardContent>
      </Card>
    );
  }

  const getRiskBadge = () => {
    switch (riskAssessment.level) {
      case "LOW":
        return <Badge variant="success">LOW RISK</Badge>;
      case "HIGH":
      case "CRITICAL":
        return <Badge variant="danger">{riskAssessment.level} RISK</Badge>;
      case "MEDIUM":
      default:
        return <Badge variant="warning">MEDIUM RISK</Badge>;
    }
  };

  const getVerdictBadge = () => {
    switch (riskAssessment.verdict) {
      case "APPROVED":
        return (
          <span className="flex items-center gap-1 text-emerald-400 font-bold">
            <CheckCircle className="h-4 w-4" /> APPROVED
          </span>
        );
      case "REJECTED":
        return (
          <span className="flex items-center gap-1 text-red-400 font-bold">
            <XCircle className="h-4 w-4" /> REJECTED
          </span>
        );
      case "CONDITIONAL":
      default:
        return (
          <span className="flex items-center gap-1 text-amber-400 font-bold">
            <AlertTriangle className="h-4 w-4" /> CONDITIONAL
          </span>
        );
    }
  };

  return (
    <Card className="border-orange-500/30 bg-orange-950/10">
      <CardHeader className="border-orange-500/20 text-orange-400">
        <div className="flex items-center justify-between">
          <CardTitle className="text-zinc-100 flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-orange-400" />
            RISK MANAGEMENT EVALUATION
          </CardTitle>

          <div className="flex items-center gap-2">
            {getRiskBadge()}
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4 space-y-4">
        {/* Risk & Verdict Summary Header */}
        <div className="rounded-lg border border-orange-500/30 bg-zinc-950/90 p-3.5 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
              COMMITTEE VERDICT
            </div>
            <div className="text-base font-mono mt-0.5">{getVerdictBadge()}</div>
          </div>

          <div className="text-right">
            <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
              RISK LEVEL
            </div>
            <div className="text-base font-bold font-mono text-zinc-100 mt-0.5">
              {riskAssessment.level}
            </div>
          </div>
        </div>

        {/* Key Risk Factors */}
        {riskAssessment.keyRisks && riskAssessment.keyRisks.length > 0 && (
          <div className="space-y-2">
            <div className="text-[11px] font-mono text-zinc-400 uppercase font-semibold flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
              IDENTIFIED RISK FACTORS
            </div>
            <div className="space-y-1.5">
              {riskAssessment.keyRisks.map((risk, idx) => (
                <div
                  key={idx}
                  className="rounded border border-zinc-800 bg-zinc-950/60 px-3 py-1.5 text-xs font-mono text-zinc-300 flex items-start gap-2"
                >
                  <span className="text-amber-400 font-bold">•</span>
                  <span>{risk}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Mitigation Rules */}
        {riskAssessment.mitigation && (
          <div className="rounded border border-zinc-800 bg-zinc-950/60 p-3 space-y-1">
            <div className="text-[11px] font-mono text-zinc-400 uppercase font-semibold">
              RISK MITIGATION DIRECTIVES
            </div>
            <p className="text-xs font-mono text-zinc-300 leading-relaxed whitespace-pre-wrap">
              {riskAssessment.mitigation}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
