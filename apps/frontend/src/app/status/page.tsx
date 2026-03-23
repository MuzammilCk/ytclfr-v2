"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function StatusLookupPage() {
  const router = useRouter();
  const [jobId, setJobId] = useState<string>("");

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const value = jobId.trim();
    if (!value) {
      return;
    }
    router.push(`/status/${value}`);
  }

  return (
    <section className="hero">
      <h1 className="title">Track your video.</h1>
      <p className="lead">Enter your tracking ID to see if your notes are ready.</p>
      <form className="stack" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="job-id">
          Tracking ID
        </label>
        <input
          autoComplete="off"
          className="text-input"
          id="job-id"
          name="job-id"
          onChange={(event) => setJobId(event.target.value)}
          placeholder="b6f9b53b-3110-4f3a-8a95-4e5cf3fcf16c"
          required
          value={jobId}
        />
        <div className="actions">
          <button className="button button-primary" type="submit">
            Check Status
          </button>
        </div>
      </form>
    </section>
  );
}
