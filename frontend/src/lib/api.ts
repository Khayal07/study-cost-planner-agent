// Thin client for the backend API. The base URL is inlined at build time from
// NEXT_PUBLIC_API_BASE_URL (see Dockerfile / .env).

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: string;
  service: string;
  llm_enabled: boolean;
  report_currency: string;
};

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend unhealthy: ${res.status}`);
  return res.json();
}
