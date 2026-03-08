"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

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

  const canSubmit = useMemo(
    () => youtubeUrl.trim().length > 0 && !isSubmitting,
    [isSubmitting, youtubeUrl],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const value = youtubeUrl.trim();
    setError(null);

    if (!isValidYoutubeUrl(value)) {
      setError("Enter a valid YouTube watch, shorts, or youtu.be URL.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await processVideo(value);
      router.push(`/status/${response.job_id}`);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unexpected error while queueing video processing.");
      }
      setIsSubmitting(false);
    }
  }

  return (
    <section className="card hero">
      <span className="eyebrow">Video to Knowledge</span>
      <h1 className="title">Turn any YouTube video into structured insights.</h1>
      <p className="lead">
        Submit a link, track pipeline progress in real time, and review extracted knowledge in one
        place.
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
            {isSubmitting ? "Queueing..." : "Process Video"}
          </button>
        </div>
      </form>

      {error ? <p className="feedback feedback-error">{error}</p> : null}
    </section>
  );
}
