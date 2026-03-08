"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function ResultLookupPage() {
  const router = useRouter();
  const [videoId, setVideoId] = useState<string>("");

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const value = videoId.trim();
    if (!value) {
      return;
    }
    router.push(`/result/${value}`);
  }

  return (
    <section className="card hero">
      <span className="eyebrow">Result</span>
      <h1 className="title">Open parsed output by video ID.</h1>
      <p className="lead">
        Use this page to fetch extracted data and generated actions for a processed video.
      </p>
      <form className="stack" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="video-id">
          Video ID
        </label>
        <input
          autoComplete="off"
          className="text-input"
          id="video-id"
          name="video-id"
          onChange={(event) => setVideoId(event.target.value)}
          placeholder="26a0f8f9-4f43-4089-a245-388f9aee29eb"
          required
          value={videoId}
        />
        <div className="actions">
          <button className="button button-primary" type="submit">
            Open Result
          </button>
        </div>
      </form>
    </section>
  );
}
