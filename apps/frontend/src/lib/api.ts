import { getApiBaseUrl } from "./config";
import type { JobStatusResponse, ProcessVideoResponse, VideoResultResponse } from "./types";

/**
 * Error wrapper for API calls.
 */
export class ApiError extends Error {
  readonly statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
  }
}

/**
 * Execute HTTP requests against YTCLFR API.
 */
async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const fallbackMessage = `API request failed with status ${response.status}.`;
    let message = fallbackMessage;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
        message = payload.detail;
      }
    } catch {
      // Ignore JSON parsing failures and keep fallback message.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

/**
 * Submit a YouTube URL for processing.
 */
export async function processVideo(youtubeUrl: string): Promise<ProcessVideoResponse> {
  return apiRequest<ProcessVideoResponse>("/api/v1/process-video", {
    method: "POST",
    body: JSON.stringify({ youtube_url: youtubeUrl }),
  });
}

/**
 * Fetch one job status.
 */
export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiRequest<JobStatusResponse>(`/api/v1/job-status/${jobId}`);
}

/**
 * Fetch parsed result by video identifier.
 */
export async function getVideoResult(videoId: string): Promise<VideoResultResponse> {
  return apiRequest<VideoResultResponse>(`/api/v1/result/${videoId}`);
}
