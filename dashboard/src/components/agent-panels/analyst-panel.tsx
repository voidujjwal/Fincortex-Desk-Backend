"use client";

/**
 * Analyst Panel Component
 * 
 * Displays individual analyst reports with color-coded borders.
 */

import { AnalystReport } from "@/lib/types/analysis";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, MessageSquare, Newspaper, BarChart3, Loader2 } from "lucide-react";

interface AnalystPanelProps {
  report: AnalystReport;
}

const agentConfig = {
  market: {
    label: "Market Analyst",
    icon: TrendingUp,
    color: "#F59E0B",
    borderColor: "border-amber-500/50",
    bgColor: "bg-amber-500/10",
    textColor: "text-amber-400",
  },
  sentiment: {
    label: "Sentiment Analyst",
    icon: MessageSquare,
    color: "#06B6D4",
    borderColor: "border-cyan-500/50",
    bgColor: "bg-cyan-500/10",
    textColor: "text-cyan-400",
  },
  news: {
    label: "News Analyst",
    icon: Newspaper,
    color: "#8B5CF6",
    borderColor: "border-violet-500/50",
    bgColor: "bg-violet-500/10",
    textColor: "text-violet-400",
  },
  fundamentals: {
    label: "Fundamentals Analyst",
    icon: BarChart3,
    color: "#10B981",
    borderColor: "border-emerald-500/50",
    bgColor: "bg-emerald-500/10",
    textColor: "text-emerald-400",
  },
};

export function AnalystPanel({ report }: AnalystPanelProps) {
  const config = agentConfig[report.agent];
  const Icon = config.icon;

  if (report.status === "pending") {
    return (
      <Card className={`border ${config.borderColor} bg-card/50 backdrop-blur-sm`}>
        <CardHeader className="pb-2">
          <CardTitle className={`text-sm font-mono ${config.textColor} flex items-center gap-2`}>
            <Icon className="w-4 h-4" />
            {config.label}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4 bg-zinc-800" />
            <Skeleton className="h-4 w-1/2 bg-zinc-800" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (report.status === "running") {
    return (
      <Card className={`border ${config.borderColor} ${config.bgColor} backdrop-blur-sm`}>
        <CardHeader className="pb-2">
          <CardTitle className={`text-sm font-mono ${config.textColor} flex items-center gap-2`}>
            <Loader2 className="w-4 h-4 animate-spin" />
            {config.label}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-zinc-400 text-sm font-mono">Analyzing data...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`border ${config.borderColor} ${config.bgColor} backdrop-blur-sm`}>
      <CardHeader className="pb-2">
        <CardTitle className={`text-sm font-mono ${config.textColor} flex items-center gap-2`}>
          <Icon className="w-4 h-4" />
          {config.label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {report.highlights && report.highlights.length > 0 ? (
          <ul className="space-y-1">
            {report.highlights.map((highlight, idx) => (
              <li
                key={idx}
                className="text-zinc-300 text-sm font-mono leading-relaxed"
              >
                <span className={config.textColor}>›</span> {highlight}
              </li>
            ))}
          </ul>
        ) : report.report ? (
          <p className="text-zinc-300 text-sm font-mono leading-relaxed line-clamp-6">
            {report.report}
          </p>
        ) : (
          <p className="text-zinc-500 text-sm font-mono">No report available</p>
        )}
      </CardContent>
    </Card>
  );
}
