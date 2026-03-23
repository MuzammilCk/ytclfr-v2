"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { ApiError, processVideo } from "../lib/api";

const ALLOWED_YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "youtu.be",
]);

function isValidYoutubeUrl(value: string): boolean {
  try {
    const parsed = new URL(value.trim());
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return false;
    }

    const host = parsed.hostname.toLowerCase();
    if (!ALLOWED_YOUTUBE_HOSTS.has(host)) {
      return false;
    }

    if (host === "youtu.be") {
      return parsed.pathname.replaceAll("/", "").length > 0;
    }

    if (parsed.pathname.startsWith("/shorts/")) {
      return parsed.pathname.replace("/shorts/", "").replaceAll("/", "").length > 0;
    }

    return parsed.pathname === "/watch" && parsed.searchParams.get("v")?.trim().length !== 0;
  } catch {
    return false;
  }
}

export default function HomePage() {
  const router = useRouter();
  const [youtubeUrl, setYoutubeUrl] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [recentJobs, setRecentJobs] = useState<{jobId: string, url: string, timestamp: string}[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("ytclfr_recent_jobs");
      if (stored) {
        setRecentJobs(JSON.parse(stored));
      }
    } catch {
      // Ignore parse errors safely
    }
  }, []);

  const canSubmit = useMemo(
    () => youtubeUrl.trim().length > 0 && !isSubmitting,
    [isSubmitting, youtubeUrl],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const value = youtubeUrl.trim();
    setError(null);

    if (!isValidYoutubeUrl(value)) {
      setError("Please enter a valid YouTube link.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await processVideo(value);
      
      const newJob = { jobId: response.job_id, url: value, timestamp: new Date().toISOString() };
      setRecentJobs((prev) => {
        const updated = [newJob, ...prev].slice(0, 10);
        localStorage.setItem("ytclfr_recent_jobs", JSON.stringify(updated));
        return updated;
      });

      router.push(`/status/${response.job_id}`);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Please try again later.");
      }
      setIsSubmitting(false);
    }
  }

  return (
    <section className="hero">
      <h1 className="title">Turn any YouTube video into clear notes and playlists.</h1>
      <p className="lead">
        Paste a link below. We'll watch the video, read the text, and organize the highlights for you automatically.
      </p>

      <form className="stack" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="youtube-url">
          YouTube URL
        </label>
        <input
          autoComplete="off"
          className="text-input"
          id="youtube-url"
          name="youtube-url"
          onChange={(event) => setYoutubeUrl(event.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          required
          type="url"
          value={youtubeUrl}
        />
        <div className="actions">
          <button className="button button-primary" disabled={!canSubmit} type="submit">
            {isSubmitting ? "Analyzing..." : "Extract Notes"}
          </button>
        </div>
      </form>

      {error ? <p className="feedback feedback-error">{error}</p> : null}

      {recentJobs.length > 0 && (
        <div className="recent-jobs-section">
          <h2>Your Recent Videos</h2>
          <ul className="recent-jobs-list">
            {recentJobs.map((job) => (
               <li key={job.jobId} className="job-item">
                 <p>
                   {new Date(job.timestamp).toLocaleString()}
                 </p>
                 <div className="job-details">
                   <span className="job-url" title={job.url}>
                     {job.url}
                   </span>
                   <Link 
                     href={`/status/${job.jobId}`}
                     className="button button-primary button-small" 
                   >
                     View Status
                   </Link>
                 </div>
               </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
