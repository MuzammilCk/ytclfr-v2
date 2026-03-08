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
    <section className="card hero">
      <span className="eyebrow">Processing Status</span>
      <h1 className="title">Check an existing job.</h1>
      <p className="lead">
        Paste a job identifier to monitor the current pipeline state and access the final result
        when processing is completed.
      </p>
      <form className="stack" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="job-id">
          Job ID
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
            Open Status
          </button>
        </div>
      </form>
    </section>
  );
}
