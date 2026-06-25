// Thin client + shared types for the backend API. Base URL is inlined at build
// time from NEXT_PUBLIC_API_BASE_URL (see Dockerfile / .env).

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: string;
  service: string;
  llm_enabled: boolean;
  report_currency: string;
};

export type Citation = {
  publisher: string;
  url: string | null;
  accessed_date: string | null;
  source_type: string;
};

export type CostLine = {
  label: string;
  cost_type: string;
  amount: number;
  currency: string;
  original_amount: number;
  original_currency: string;
  original_period: string;
  confidence: "sourced" | "estimate";
  note: string | null;
  converted: boolean;
  citation: Citation;
};

export type ScenarioBreakdown = {
  name: string;
  multiplier: number;
  annual_total: number;
  monthly_living: number;
  budget_gap: number;
  narrative: string | null;
};

export type CandidatePlan = {
  program_id: number;
  program_name: string;
  field: string;
  degree_level: string;
  language: string;
  duration_years: number;
  university_name: string;
  university_url: string | null;
  city_name: string;
  country_name: string;
  country_iso: string;
  report_currency: string;
  lines: CostLine[];
  annual_tuition: number;
  annual_living: number;
  annual_one_time: number;
  annual_hidden: number;
  total_annual: number;
  monthly_living: number;
  fx_notes: string[];
  scenarios: ScenarioBreakdown[];
  budget_gap: number | null;
  affordable: boolean | null;
  rank: number | null;
};

export type VerificationCheck = { name: string; status: string; detail: string };
export type VerificationReport = {
  overall: string;
  checks: VerificationCheck[];
  summary: string | null;
};

export type PlanningRequest = {
  country?: string | null;
  field?: string | null;
  degree_level?: string | null;
  budget_amount: number;
  budget_currency: string;
  report_currency: string;
  lifestyle?: string;
  max_results?: number;
  // The university the report should feature (selected card / discussed in chat).
  focus_program_id?: number | null;
};

export type PlanResult = {
  request: PlanningRequest;
  report_currency: string;
  candidates: CandidatePlan[];
  verification: VerificationReport | null;
  recommendations: string[];
  generated_at: string;
  disclaimer: string;
};

export type CitedFigure = {
  label: string;
  amount: number;
  currency: string;
  confidence: string;
  citation: Citation;
};

export type ChatCandidateRef = {
  rank: number;
  program_id: number;
  program_name: string;
  university_name: string;
  city_name: string;
  country_name: string;
  total_annual: number;
  affordable: boolean | null;
  match_score: number | null;
};

export type ChatProfile = {
  country: string | null;
  field: string | null;
  degree_level: string | null;
  budget_amount: number | null;
  budget_currency: string | null;
  lifestyle: string | null;
  report_currency: string;
  last_candidates: ChatCandidateRef[];
  focus_program_id: number | null;
  turn: number;
};

export type ChatSuggestion = { label: string; message: string };

export type ChatMode =
  | "greeting"
  | "discovery"
  | "detail"
  | "compare"
  | "affordability"
  | "answer"
  | "clarify";

export type ChatResponse = {
  mode: ChatMode;
  answer: string;
  profile: ChatProfile;
  suggestions: ChatSuggestion[];
  extracted: Record<string, unknown>;
  figures: CitedFigure[];
  candidates: CandidatePlan[];
  detail: CandidatePlan | null;
  plan: PlanResult | null;
  can_export: boolean;
};

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend unhealthy: ${res.status}`);
  return res.json();
}

export async function postPlan(req: PlanningRequest): Promise<PlanResult> {
  const res = await fetch(`${API_BASE_URL}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Plan failed: ${res.status}`);
  return res.json();
}

export async function postChat(
  message: string,
  report_currency: string,
  profile: ChatProfile | null,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, report_currency, profile }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

// Build the PlanningRequest the advisor's profile implies, for the PDF export.
export function profileToPlanRequest(profile: ChatProfile): PlanningRequest {
  return {
    country: profile.country,
    field: profile.field ?? "Computer Science",
    degree_level: profile.degree_level,
    budget_amount: profile.budget_amount ?? 0,
    budget_currency: profile.budget_currency ?? profile.report_currency,
    report_currency: profile.report_currency,
    lifestyle: profile.lifestyle ?? "moderate",
    // Feature the university the advisor is focused on (the one discussed/asked about).
    focus_program_id: profile.focus_program_id,
  };
}

// Download the PDF: POST JSON, receive a blob, trigger a browser download.
export async function exportPdf(req: PlanningRequest): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`PDF export failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "study-cost-plan.pdf";
  a.click();
  URL.revokeObjectURL(url);
}
