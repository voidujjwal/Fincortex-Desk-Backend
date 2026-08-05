"use client";

/**
 * Analysis Form Component
 * 
 * Provides input fields for ticker symbol and analysis date,
 * along with submit and reset buttons.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Play, RotateCcw, Loader2 } from "lucide-react";

interface AnalysisFormProps {
  onSubmit: (ticker: string, date: string) => void;
  onReset: () => void;
  isLoading: boolean;
}

export function AnalysisForm({
  onSubmit,
  onReset,
  isLoading,
}: AnalysisFormProps) {
  const [ticker, setTicker] = useState("");
  const [date, setDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split("T")[0];
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim() && !isLoading) {
      onSubmit(ticker.trim().toUpperCase(), date);
    }
  };

  const handleReset = () => {
    setTicker("");
    const today = new Date();
    setDate(today.toISOString().split("T")[0]);
    onReset();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="ticker" className="text-zinc-400 text-xs uppercase tracking-wider">
            Ticker Symbol
          </Label>
          <Input
            id="ticker"
            type="text"
            placeholder="e.g., AAPL"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="bg-terminal-light border-zinc-700 text-white placeholder:text-zinc-600 font-mono uppercase"
            disabled={isLoading}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="date" className="text-zinc-400 text-xs uppercase tracking-wider">
            Analysis Date
          </Label>
          <Input
            id="date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="bg-terminal-light border-zinc-700 text-white font-mono"
            disabled={isLoading}
          />
        </div>
      </div>

      <div className="flex gap-3">
        <Button
          type="submit"
          disabled={!ticker.trim() || isLoading}
          className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-mono"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Play className="w-4 h-4 mr-2" />
              Run Analysis
            </>
          )}
        </Button>

        <Button
          type="button"
          variant="outline"
          onClick={handleReset}
          disabled={isLoading}
          className="border-zinc-700 text-zinc-400 hover:text-white hover:bg-zinc-800"
        >
          <RotateCcw className="w-4 h-4 mr-2" />
          Reset
        </Button>
      </div>
    </form>
  );
}
