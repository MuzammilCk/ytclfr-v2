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
    <section className="hero">
      <h1 className="title">View your results.</h1>
      <p className="lead">Enter your Video ID to access playlists, recipes, movie lists, and more.</p>
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
            View Results
          </button>
        </div>
      </form>
    </section>
  );
}
