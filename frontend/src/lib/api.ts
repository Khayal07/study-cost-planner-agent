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

export type ScholarshipEligibility =
  | "eligible"
  | "likely"
  | "unknown"
  | "ineligible";

export type ScholarshipMatch = {
  scholarship_id: number;
  name: string;
  provider: string;
  coverage_type: string;
  amount: number | null;
  coverage_pct: number | null;
  currency: string;
  estimated_value: number;
  eligibility: ScholarshipEligibility;
  match_score: number;
  reasons: string[];
  tips: string[];
  deadline: string | null;
  days_until_deadline: number | null;
  renewable: boolean;
  application_url: string | null;
  documents_required: string[];
  citation: Citation;
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
  // Scholarship layer
  scholarships: ScholarshipMatch[];
  total_scholarship_value: number;
  net_total_annual: number | null;
  net_budget_gap: number | null;
  net_affordable: boolean | null;
  value_rank: number | null;
  // Part-time work offset (Phase 3 #7)
  work_hours_cap: number | null;
  work_annual_earnings: number | null;
  work_note: string | null;
  work_citation: Citation | null;
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
  // Optional eligibility inputs for scholarship matching.
  nationality?: string | null;
  gpa?: number | null;
  language_test?: string | null;
  // User-selected live (web-found) scholarships to fold into the PDF + net total.
  extra_scholarships?: LiveScholarship[];
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
  nationality: string | null;
  gpa: number | null;
  language_test: string | null;
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
  | "scholarships"
  | "value"
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

// --- Accounts + application tracker (Phase H) ---

export type UserOut = {
  id: number;
  email: string;
  nationality: string | null;
  gpa: number | null;
  language_test: string | null;
};

export type AuthResponse = { token: string; user: UserOut };

export type ApplicationTask = {
  scholarship_id: number;
  name: string;
  provider: string;
  university_name: string;
  program_id: number;
  coverage_type: string;
  estimated_value: number;
  currency: string;
  eligibility: string;
  deadline: string | null;
  days_until_deadline: number | null;
  priority: number;
  priority_reason: string;
  application_url: string | null;
  documents: string[];
};

export type ApplicationPlan = {
  tasks: ApplicationTask[];
  this_week: string[];
  all_documents: string[];
  generated_at: string;
};

export type DocumentOut = { id: number; name: string; done: boolean };

export type ApplicationOut = {
  id: number;
  scholarship_id: number | null;
  program_id: number | null;
  scholarship_name: string;
  provider: string | null;
  university_name: string | null;
  coverage_type: string | null;
  estimated_value: number | null;
  currency: string | null;
  deadline: string | null;
  days_until_deadline: number | null;
  application_url: string | null;
  status: string;
  notes: string | null;
  motivation_letter: string | null;
  documents: DocumentOut[];
};

export type ApplicationCreate = {
  scholarship_id?: number | null;
  program_id?: number | null;
  scholarship_name: string;
  provider?: string | null;
  university_name?: string | null;
  coverage_type?: string | null;
  estimated_value?: number | null;
  currency?: string | null;
  deadline?: string | null;
  application_url?: string | null;
  documents?: string[];
};

// --- Saved plans + shareable links (Phase 3 #4) ---

export type SavedPlanOut = {
  id: number;
  public_id: string;
  title: string;
  created_at: string;
  request: PlanningRequest;
};

export type SavedPlanDetail = {
  public_id: string;
  title: string;
  created_at: string;
  request: PlanningRequest;
  plan: PlanResult;
};

const TOKEN_KEY = "scp-token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function authed(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? "Registration failed");
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? "Login failed");
  return res.json();
}

export async function getMe(): Promise<UserOut> {
  const res = await authed("/auth/me");
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

export async function planApplications(req: PlanningRequest): Promise<ApplicationPlan> {
  const res = await fetch(`${API_BASE_URL}/applications/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Planner failed: ${res.status}`);
  return res.json();
}

export async function listApplications(): Promise<ApplicationOut[]> {
  const res = await authed("/applications");
  if (!res.ok) throw new Error("Failed to load applications");
  return res.json();
}

export async function createApplication(body: ApplicationCreate): Promise<ApplicationOut> {
  const res = await authed("/applications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to save application");
  return res.json();
}

export async function updateApplication(
  id: number,
  body: { status?: string; notes?: string; motivation_letter?: string },
): Promise<ApplicationOut> {
  const res = await authed(`/applications/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update application");
  return res.json();
}

export async function toggleDocument(
  appId: number,
  docId: number,
  done: boolean,
): Promise<ApplicationOut> {
  const res = await authed(`/applications/${appId}/documents/${docId}?done=${done}`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error("Failed to update document");
  return res.json();
}

export async function deleteApplication(id: number): Promise<void> {
  const res = await authed(`/applications/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("Failed to delete application");
}

export async function saveCurrentPlan(title: string, request: PlanningRequest): Promise<SavedPlanOut> {
  const res = await authed("/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, request }),
  });
  if (!res.ok) throw new Error("Failed to save plan");
  return res.json();
}

export async function listSavedPlans(): Promise<SavedPlanOut[]> {
  const res = await authed("/plans");
  if (!res.ok) throw new Error("Failed to load saved plans");
  return res.json();
}

export async function getSharedPlan(publicId: string): Promise<SavedPlanDetail> {
  const res = await fetch(`${API_BASE_URL}/plans/shared/${publicId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Plan not found");
  return res.json();
}

export async function deleteSavedPlan(id: number): Promise<void> {
  const res = await authed(`/plans/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("Failed to delete plan");
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend unhealthy: ${res.status}`);
  return res.json();
}

export interface CatalogOptions {
  countries: string[];
  fields: string[];
  report_currencies: string[];
  default_report_currency: string;
}

export async function getOptions(): Promise<CatalogOptions> {
  const res = await fetch(`${API_BASE_URL}/meta/options`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Options failed: ${res.status}`);
  return res.json();
}

export interface DatasetStats {
  countries: number;
  universities: number;
  programs: number;
  cited_figures: number;
  sourced_figures: number;
  scholarships: number;
}

export async function getStats(): Promise<DatasetStats> {
  const res = await fetch(`${API_BASE_URL}/meta/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Stats failed: ${res.status}`);
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

// --- Live scholarship search (web-sourced, AI-fetched) ---

export interface LiveScholarship {
  name: string;
  provider: string | null;
  amount: string | null;
  coverage_type: string | null;
  deadline: string | null;
  eligibility: string | null;
  official_url: string | null;
  annual_value: number | null;
}

export interface LiveScholarshipSearchResponse {
  results: LiveScholarship[];
  cached: boolean;
  limited: boolean;
  note: string | null;
}

export async function searchLiveScholarships(
  country: string,
  field: string,
  degree_level: string | null,
  report_currency: string,
): Promise<LiveScholarshipSearchResponse> {
  const res = await fetch(`${API_BASE_URL}/scholarships/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ country, field, degree_level, report_currency }),
  });
  if (!res.ok) throw new Error(`Live scholarship search failed: ${res.status}`);
  return res.json();
}

// --- Profile (eligibility) ---

export async function updateProfile(body: {
  nationality: string | null;
  gpa: number | null;
  language_test: string | null;
}): Promise<UserOut> {
  const res = await authed("/auth/me/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Profile update failed: ${res.status}`);
  return res.json();
}

// --- Transcript analysis (auth; user confirms before the profile is written) ---

export type TranscriptExtraction = {
  gpa: number | null;
  gpa_scale: number | null;
  gpa_on_4_scale: number | null;
  degree_level: string | null;
  institution: string | null;
  confidence: string;
};

export type TranscriptAnalysisResponse = {
  extraction: TranscriptExtraction;
  note: string | null;
};

export async function analyzeTranscript(file: File): Promise<TranscriptAnalysisResponse> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await authed("/profile/transcript", { method: "POST", body: fd });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : `Analysis failed: ${res.status}`);
  }
  return res.json();
}

// --- Voice transcription (whisper -> chat input) ---

export type TranscribeResponse = {
  text: string;
  language: string | null;
  limited: boolean;
};

export async function transcribeAudio(blob: Blob, language: "az" | "en" | ""): Promise<TranscribeResponse> {
  const fd = new FormData();
  const type = blob.type || "audio/webm";
  const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "mp4" : type.includes("wav") ? "wav" : "webm";
  fd.append("file", new File([blob], `voice.${ext}`, { type }));
  fd.append("language", language);
  const res = await fetch(`${API_BASE_URL}/chat/transcribe`, { method: "POST", body: fd });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : `Transcription failed: ${res.status}`);
  }
  return res.json();
}

// --- Motivation letter generator (auth) ---

export type MotivationLetterResponse = {
  letter: string;
  language: string;
  saved: boolean;
};

export async function generateMotivationLetter(body: {
  application_id?: number | null;
  scholarship_name: string;
  provider?: string | null;
  university_name?: string | null;
  program_name?: string | null;
  language?: "en" | "az";
  tone?: "formal" | "personal";
  user_notes?: string | null;
}): Promise<MotivationLetterResponse> {
  const res = await authed("/letters/motivation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : `Letter failed: ${res.status}`);
  }
  return res.json();
}

// --- Interview simulator (stateless, /chat prefix) ---

export type InterviewTurn = { role: "interviewer" | "student"; content: string };

export type InterviewFeedback = {
  strengths: string[];
  improvements: string[];
  overall: string;
};

export type InterviewResponse = {
  message: string;
  done: boolean;
  feedback: InterviewFeedback | null;
  question_count: number;
};

export async function postInterview(body: {
  context?: {
    scholarship_name?: string | null;
    university_name?: string | null;
    program_name?: string | null;
    field?: string | null;
  };
  history: InterviewTurn[];
  action: "start" | "reply" | "finish";
  language?: "en" | "az";
}): Promise<InterviewResponse> {
  const res = await fetch(`${API_BASE_URL}/chat/interview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Interview failed: ${res.status}`);
  return res.json();
}

// --- Cost forecast (deterministic projection + optional AI commentary) ---

export type ForecastYear = {
  year_offset: number;
  year_label: string;
  tuition: number;
  living: number;
  total: number;
};

export type ForecastResponse = {
  series: ForecastYear[];
  assumptions: {
    tuition_inflation_pct: number;
    living_inflation_pct: number;
    note: string;
  };
  commentary: string | null;
};

export async function postForecast(body: {
  country_iso: string | null;
  country_name: string;
  annual_tuition: number;
  annual_living: number;
  currency: string;
  years?: number;
  with_commentary?: boolean;
  language?: "en" | "az";
}): Promise<ForecastResponse> {
  const res = await fetch(`${API_BASE_URL}/forecast`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Forecast failed: ${res.status}`);
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
    nationality: profile.nationality,
    gpa: profile.gpa,
    language_test: profile.language_test,
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
  // Use the server's per-university filename when provided.
  const disp = res.headers.get("Content-Disposition") ?? "";
  const match = disp.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? "study-cost-plan.pdf";
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
