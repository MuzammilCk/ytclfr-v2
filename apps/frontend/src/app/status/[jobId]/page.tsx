"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, getJobStatus } from "../../../lib/api";
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

function getStatusClass(status: JobStatus): string {
  const normalized = status.toUpperCase();
  if (normalized === "COMPLETED") {
    return "status-pill status-completed";
  }
  if (normalized === "FAILED") {
    return "status-pill status-failed";
  }
  if (normalized === "RUNNING") {
    return "status-pill status-running";
  }
  return "status-pill status-pending";
}

function getProgressPercent(status: JobStatus): number {
  const normalized = status.toUpperCase();
  if (normalized === "COMPLETED" || normalized === "FAILED") {
    return 100;
  }
  if (normalized === "RUNNING") {
    return 65;
  }
  return 20;
}

function getSteps(status: JobStatus): PipelineStep[] {
  const normalized = status.toUpperCase();
  const queued = normalized === "PENDING" || normalized === "RUNNING" || normalized === "COMPLETED" || normalized === "FAILED";
  const processing = normalized === "RUNNING" || normalized === "COMPLETED" || normalized === "FAILED";
  const generated = normalized === "COMPLETED";

  return [
    { label: "Job queued", active: queued },
    { label: "Download + frame extraction + OCR", active: processing },
    { label: "AI parsing + output generation", active: processing },
    { label: "Completed", active: generated },
  ];
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function JobStatusPage({ params }: JobStatusPageProps) {
  const [status, setStatus] = useState<JobStatus>("PENDING");
  const [videoId, setVideoId] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [requestError, setRequestError] = useState<string | null>(null);

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

  useEffect(() => {
    let active = true;
    let timerId: ReturnType<typeof setInterval> | undefined;

    const run = async (): Promise<void> => {
      if (!active) {
        return;
      }
      await pollStatus();
    };

    void run();
    timerId = setInterval(() => {
      if (status.toUpperCase() === "COMPLETED" || status.toUpperCase() === "FAILED") {
        if (timerId) {
          clearInterval(timerId);
        }
        return;
      }
      void run();
    }, 4000);

    return () => {
      active = false;
      if (timerId) {
        clearInterval(timerId);
      }
    };
  }, [pollStatus, status]);

  const steps = useMemo(() => getSteps(status), [status]);
  const progressPercent = useMemo(() => getProgressPercent(status), [status]);

  return (
    <section className="card hero">
      <span className="eyebrow">Processing Status</span>
      <h1 className="title">Job {params.jobId}</h1>
      <p className="lead">This page automatically refreshes while the pipeline is in progress.</p>

      {isLoading ? <p className="feedback">Loading latest status...</p> : null}
      {requestError ? <p className="feedback feedback-error">{requestError}</p> : null}

      <div className="status-grid">
        <div>
          <span className={getStatusClass(status)}>{status.toUpperCase()}</span>
          {updatedAt ? <p className="meta">Updated: {formatTimestamp(updatedAt)}</p> : null}
          {errorMessage ? <p className="feedback feedback-error">{errorMessage}</p> : null}
        </div>

        <div className="progress-track" role="progressbar" aria-valuenow={progressPercent}>
          <div className="progress-value" style={{ width: `${progressPercent}%` }} />
        </div>

        <div className="timeline">
          {steps.map((step) => (
            <div className="timeline-row" key={step.label}>
              <span className={`timeline-dot ${step.active ? "timeline-active" : ""}`} />
              <span className="timeline-text">{step.label}</span>
            </div>
          ))}
        </div>

        <div className="actions">
          <button className="button button-secondary" onClick={() => void pollStatus()} type="button">
            Refresh now
          </button>
          {videoId ? (
            <Link className="button button-primary" href={`/result/${videoId}`}>
              View Result
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  );
}
