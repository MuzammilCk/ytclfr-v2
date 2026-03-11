/**
 * API status values for pipeline jobs.
 */
export type JobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | string;

/**
 * API response for job creation.
 */
export interface ProcessVideoResponse {
  job_id: string;
}

/**
 * API response for job status.
 */
export interface JobStatusResponse {
  job_id: string;
  video_id: string | null;
  status: JobStatus;
  error_message: string | null;
  updated_at: string;
}

/**
 * One parsed knowledge/result item.
 */
export interface ResultItem {
  title: string;
  description: string;
  tags: string[];
  action_output?: Record<string, unknown> | null;
}

/**
 * API response for video result fetch.
 */
export interface VideoResultResponse {
  video_id: string;
  items: ResultItem[];
}
