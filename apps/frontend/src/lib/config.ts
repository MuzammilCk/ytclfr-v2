/**
 * Resolve API base URL from environment with runtime validation.
 */
export function getApiBaseUrl(): string {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!value) {
    throw new Error(
      "Missing NEXT_PUBLIC_API_BASE_URL environment variable for frontend API calls.",
    );
  }
  return value.replace(/\/+$/, "");
}
