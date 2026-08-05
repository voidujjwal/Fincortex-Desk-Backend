/**
 * API Route for TradingAgents Analysis
 * 
 * This route spawns a Python subprocess that runs TradingAgents
 * and streams the output back via Server-Sent Events (SSE).
 */

import { spawn } from "child_process";
import { NextRequest } from "next/server";
import path from "path";

interface AnalyzeRequest {
  ticker: string;
  date: string;
}

export async function POST(request: NextRequest) {
  let body: AnalyzeRequest;

  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  const { ticker, date } = body;

  // Validate inputs
  if (!ticker || typeof ticker !== "string" || ticker.trim().length === 0) {
    return new Response(
      JSON.stringify({ error: "Ticker is required" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  if (!date || typeof date !== "string") {
    return new Response(
      JSON.stringify({ error: "Date is required" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  // Validate date format (YYYY-MM-DD)
  const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
  if (!dateRegex.test(date)) {
    return new Response(
      JSON.stringify({ error: "Date must be in YYYY-MM-DD format" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  // Get the path to the Python runner script
  const runnerScript = path.join(
    process.cwd(),
    "..",
    "dashboard",
    "python-runner",
    "trading_agents_runner.py"
  );

  // Get Python executable path from env or default to python3/python
  const pythonExec = process.env.PYTHON_PATH || "python3";

  // Create a readable stream for SSE
  const stream = new ReadableStream({
    start(controller) {
      let eventId = 0;

      // Spawn Python subprocess
      const pythonProcess = spawn(pythonExec, [runnerScript, ticker.toUpperCase(), date], {
        cwd: process.cwd(),
        env: {
          ...process.env,
          PYTHONPATH: path.join(process.cwd(), ".."),
        },
      });

      let buffer = "";

      pythonProcess.stdout.on("data", (data: Buffer) => {
        buffer += data.toString();
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.trim()) {
            try {
              const event = JSON.parse(line);
              eventId++;
              const sseEvent = `id: ${eventId}\nevent: ${event.event}\ndata: ${JSON.stringify(event)}\n\n`;
              controller.enqueue(new TextEncoder().encode(sseEvent));
            } catch {
              // If not valid JSON, emit as log event
              eventId++;
              const sseEvent = `id: ${eventId}\nevent: log\ndata: ${JSON.stringify({ message: line })}\n\n`;
              controller.enqueue(new TextEncoder().encode(sseEvent));
            }
          }
        }
      });

      pythonProcess.stderr.on("data", (data: Buffer) => {
        const message = data.toString().trim();
        if (message) {
          eventId++;
          const sseEvent = `id: ${eventId}\nevent: error\ndata: ${JSON.stringify({ type: "stderr", message })}\n\n`;
          controller.enqueue(new TextEncoder().encode(sseEvent));
        }
      });

      pythonProcess.on("close", (code: number | null) => {
        // Send any remaining buffered data
        if (buffer.trim()) {
          try {
            const event = JSON.parse(buffer.trim());
            eventId++;
            const sseEvent = `id: ${eventId}\nevent: ${event.event}\ndata: ${JSON.stringify(event)}\n\n`;
            controller.enqueue(new TextEncoder().encode(sseEvent));
          } catch {
            // Ignore parse errors on close
          }
        }

        eventId++;
        const closeEvent = `id: ${eventId}\nevent: close\ndata: ${JSON.stringify({ code })}\n\n`;
        controller.enqueue(new TextEncoder().encode(closeEvent));
        controller.close();
      });

      pythonProcess.on("error", (error: Error) => {
        eventId++;
        const errorEvent = `id: ${eventId}\nevent: error\ndata: ${JSON.stringify({ type: "spawn_error", message: error.message })}\n\n`;
        controller.enqueue(new TextEncoder().encode(errorEvent));
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
