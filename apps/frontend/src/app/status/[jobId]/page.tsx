"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, getJobStatus } from "../../../lib/api";
import { getApiBaseUrl } from "../../../lib/config";
import type { JobStatus } from "../../../lib/types";

interface JobStatusPageProps {
  params: {
    jobId: string;
  };
}

interface PipelineStep {
  label: string;
  active: boolean;
}

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

function getStatusClass(status: JobStatus): string {
  const normalized = status.toUpperCase();
  if (normalized === "COMPLETED") return "status-pill status-completed";
  if (normalized === "FAILED") return "status-pill status-failed";
  if (normalized === "RUNNING") return "status-pill status-running";
  return "status-pill status-pending";
}

function getProgressPercent(status: JobStatus): number {
  const normalized = status.toUpperCase();
  if (normalized === "COMPLETED" || normalized === "FAILED") return 100;
  if (normalized === "RUNNING") return 65;
  return 20;
}

function getSteps(status: JobStatus): PipelineStep[] {
  const normalized = status.toUpperCase();
  const queued =
    normalized === "PENDING" ||
    normalized === "RUNNING" ||
    normalized === "COMPLETED" ||
    normalized === "FAILED";
  const processing =
    normalized === "RUNNING" ||
    normalized === "COMPLETED" ||
    normalized === "FAILED";
  const generated = normalized === "COMPLETED";

  return [
    { label: "Waiting in line", active: queued },
    { label: "Watching the video and reading text", active: processing },
    { label: "Organizing the notes", active: processing },
    { label: "Ready to view", active: generated },
  ];
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function isTerminal(status: JobStatus): boolean {
  const normalized = status.toUpperCase();
  return normalized === "COMPLETED" || normalized === "FAILED";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function JobStatusPage({ params }: JobStatusPageProps) {
  const [status, setStatus] = useState<JobStatus>("PENDING");
  const [videoId, setVideoId] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [connectionMode, setConnectionMode] = useState<"sse" | "polling">("sse");

  // Track whether SSE has been successfully established so we can
  // fall back to polling only when EventSource is unavailable.
  const sseRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  // ------------------------------------------------------------------
  // REST fallback — used when SSE is unavailable or fails
  // ------------------------------------------------------------------
  const pollStatus = useCallback(async (): Promise<void> => {
    try {
      const response = await getJobStatus(params.jobId);
      setStatus(response.status);
      setVideoId(response.video_id);
      setUpdatedAt(response.updated_at);
      setErrorMessage(response.error_message);
      setRequestError(null);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setRequestError(err.message);
      } else {
        setRequestError("Failed to fetch job status.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [params.jobId]);

  // ------------------------------------------------------------------
  // SSE subscription
  // ------------------------------------------------------------------
  useEffect(() => {
    let active = true;

    // Perform an initial REST fetch so the page shows the current state
    // immediately while the SSE connection is being established.
    void pollStatus();

    // Attempt SSE connection.
    const sseUrl = `${getApiBaseUrl()}/api/v1/job-events/${params.jobId}`;
    let source: EventSource;

    try {
      source = new EventSource(sseUrl);
      sseRef.current = source;
    } catch {
      // EventSource unavailable (e.g. test env) — fall back to polling.
      setConnectionMode("polling");
      return;
    }

    source.addEventListener("status_update", (event: MessageEvent) => {
      if (!active) return;
      try {
        const data = JSON.parse(event.data) as {
          status: JobStatus;
          video_id: string | null;
          error_message: string | null;
          timestamp: string;
        };
        setStatus(data.status);
        setVideoId(data.video_id);
        setUpdatedAt(data.timestamp);
        setErrorMessage(data.error_message);
        setIsLoading(false);
        setRequestError(null);
      } catch {
        // Malformed event — ignore.
      }
    });

    source.addEventListener("stream_end", () => {
      source.close();
      sseRef.current = null;
    });

    source.addEventListener("heartbeat", () => {
      // Heartbeat received — connection is still alive.
    });

    source.onerror = () => {
      // SSE error (network drop, server restart, etc.)
      // Fall back to polling so the page stays live.
      source.close();
      sseRef.current = null;
      if (!active) return;
      setConnectionMode("polling");
    };

    return () => {
      active = false;
      source.close();
      sseRef.current = null;
    };
  }, [params.jobId, pollStatus]);

  // ------------------------------------------------------------------
  // Polling fallback — only active when SSE has failed
  // ------------------------------------------------------------------
  useEffect(() => {
    if (connectionMode !== "polling") return;

    // Clear any existing interval before setting a new one.
    if (pollTimerRef.current !== undefined) {
      clearInterval(pollTimerRef.current);
    }

    void pollStatus();
    pollTimerRef.current = setInterval(() => {
      if (isTerminal(status)) {
        clearInterval(pollTimerRef.current);
        return;
      }
      void pollStatus();
    }, 4000);

    return () => {
      if (pollTimerRef.current !== undefined) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [connectionMode, status, pollStatus]);

  // ------------------------------------------------------------------
  // Stop polling when SSE delivers a terminal state
  // ------------------------------------------------------------------
  useEffect(() => {
    if (isTerminal(status) && pollTimerRef.current !== undefined) {
      clearInterval(pollTimerRef.current);
    }
  }, [status]);

  const steps = useMemo(() => getSteps(status), [status]);
  const progressPercent = useMemo(() => getProgressPercent(status), [status]);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <section className="hero">
      <h1 className="title">Tracking ID: {params.jobId}</h1>
      <p className="lead">
        {connectionMode === "sse"
          ? "Live updates straight from our servers."
          : "Checking for updates every few seconds..."}
      </p>

      {isLoading ? <p className="feedback">Loading latest status...</p> : null}
      {requestError ? (
        <p className="feedback feedback-error">{requestError}</p>
      ) : null}

      <div className="status-grid">
        <div>
          <span className={getStatusClass(status)}>{status.toUpperCase()}</span>
          {updatedAt ? (
            <p className="meta">Updated: {formatTimestamp(updatedAt)}</p>
          ) : null}
          {errorMessage ? (
            <p className="feedback feedback-error">{errorMessage}</p>
          ) : null}
        </div>

        <div
          className="progress-track"
          role="progressbar"
          aria-valuenow={progressPercent}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="progress-value"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        <div className="timeline">
          {steps.map((step) => (
            <div className="timeline-row" key={step.label}>
              <span
                className={`timeline-dot ${step.active ? "timeline-active" : ""}`}
              />
              <span className="timeline-text">{step.label}</span>
            </div>
          ))}
        </div>

        <div className="actions">
          <button
            className="button button-secondary"
            onClick={() => void pollStatus()}
            type="button"
          >
            Refresh now
          </button>
          {videoId ? (
            <Link
              className="button button-primary"
              href={`/result/${videoId}`}
            >
              View Result
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  );
}
