"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { getOptions, type PlanningRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { TranscriptUpload } from "./TranscriptUpload";

// Fallback only — live lists come from /meta/options so new countries/currencies
// appear automatically once their data is seeded.
const FALLBACK_COUNTRIES = ["Germany", "Netherlands", "Poland", "Hungary", "Turkey", "Czechia", "Italy"];
const FALLBACK_CURRENCIES = ["EUR", "USD", "TRY", "PLN", "HUF", "CZK", "AZN", "GBP"];

const LIFESTYLES = [
  { id: "frugal", labelKey: "wiz.lf.frugal", blurbKey: "wiz.lf.frugal.blurb" },
  { id: "moderate", labelKey: "wiz.lf.moderate", blurbKey: "wiz.lf.moderate.blurb" },
  { id: "comfortable", labelKey: "wiz.lf.comfortable", blurbKey: "wiz.lf.comfortable.blurb" },
];

const STEP_KEYS = ["wiz.s.study", "wiz.s.budget", "wiz.s.lifestyle", "wiz.s.eligibility"] as const;

export function OnboardingWizard({
  onSubmit,
  loading,
  initialCountry,
}: {
  onSubmit: (req: PlanningRequest) => void;
  loading: boolean;
  initialCountry?: string | null;
}) {
  const reduce = useReducedMotion();
  const { t } = useI18n();
  const [step, setStep] = useState(0);
  const [dir, setDir] = useState(1);

  const [field, setField] = useState("Computer Science");
  const [country, setCountry] = useState("");

  // Pre-fill the destination when the user picks a country on the map.
  useEffect(() => {
    if (initialCountry) setCountry(initialCountry);
  }, [initialCountry]);
  const [budget, setBudget] = useState(10000);
  const [budgetCurrency, setBudgetCurrency] = useState("EUR");
  const [reportCurrency, setReportCurrency] = useState("EUR");
  const [lifestyle, setLifestyle] = useState("moderate");
  const [nationality, setNationality] = useState("");
  const [gpa, setGpa] = useState("");
  const [languageTest, setLanguageTest] = useState("");

  const [countries, setCountries] = useState<string[]>(FALLBACK_COUNTRIES);
  const [currencies, setCurrencies] = useState<string[]>(FALLBACK_CURRENCIES);
  const [errors, setErrors] = useState<{ field?: string; budget?: string; gpa?: string }>({});

  useEffect(() => {
    getOptions()
      .then((opts) => {
        if (opts.countries.length) setCountries(opts.countries);
        if (opts.report_currencies?.length) setCurrencies(opts.report_currencies);
      })
      .catch(() => {
        /* keep fallback lists if the catalog call fails */
      });
  }, []);

  const budgetError = useMemo(
    () => (!Number.isFinite(budget) || budget <= 0 ? "Enter a budget greater than 0." : undefined),
    [budget],
  );
  const gpaError = useMemo(() => {
    if (!gpa.trim()) return undefined;
    const g = Number(gpa);
    return Number.isNaN(g) || g < 0 || g > 4 ? "GPA must be between 0 and 4." : undefined;
  }, [gpa]);

  function validateStep(s: number): boolean {
    const next: typeof errors = {};
    if (s === 0 && !field.trim()) next.field = "Enter a field of study.";
    if (s === 1 && budgetError) next.budget = budgetError;
    if (s === 3 && gpaError) next.gpa = gpaError;
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function go(delta: number) {
    if (delta > 0 && !validateStep(step)) return;
    setDir(delta);
    setStep((s) => Math.min(STEP_KEYS.length - 1, Math.max(0, s + delta)));
  }

  function submit() {
    if (!validateStep(1) || !validateStep(3)) return;
    const gpaNum = gpa.trim() ? Number(gpa) : null;
    onSubmit({
      country: country || null,
      field,
      budget_amount: budget,
      budget_currency: budgetCurrency,
      report_currency: reportCurrency,
      lifestyle,
      max_results: 8,
      nationality: nationality.trim() || null,
      gpa: gpaNum != null && !Number.isNaN(gpaNum) ? gpaNum : null,
      language_test: languageTest.trim() || null,
    });
  }

  const isLast = step === STEP_KEYS.length - 1;
  const variants = {
    enter: (d: number) => ({ opacity: 0, x: reduce ? 0 : d * 24 }),
    center: { opacity: 1, x: 0 },
    exit: (d: number) => ({ opacity: 0, x: reduce ? 0 : d * -24 }),
  };

  return (
    <div className="card overflow-hidden">
      {/* Header + progress */}
      <div className="border-b border-border bg-surface-2/60 px-5 py-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-base font-semibold leading-none">{t("wiz.title")}</h2>
          <span className="figure text-xs text-muted">
            {t("wiz.step")} {step + 1} / {STEP_KEYS.length}
          </span>
        </div>
        <div className="mt-3 flex gap-1.5" role="list" aria-label="Progress">
          {STEP_KEYS.map((labelKey, i) => (
            <div key={labelKey} className="flex-1" role="listitem" aria-current={i === step}>
              <div className="h-1.5 overflow-hidden rounded-full bg-border">
                <motion.div
                  className="h-full rounded-full bg-primary"
                  initial={false}
                  animate={{ width: i < step ? "100%" : i === step ? "55%" : "0%" }}
                  transition={{ duration: reduce ? 0 : 0.35, ease: [0.16, 1, 0.3, 1] }}
                />
              </div>
              <span
                className={`mt-1 block text-[10px] font-medium ${
                  i === step ? "text-primary" : "text-muted"
                }`}
              >
                {t(labelKey)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="relative min-h-[300px] p-5">
        <AnimatePresence mode="wait" custom={dir} initial={false}>
          <motion.div
            key={step}
            custom={dir}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: reduce ? 0 : 0.28, ease: [0.16, 1, 0.3, 1] }}
            className="space-y-4"
          >
            {step === 0 && (
              <>
                <div>
                  <label htmlFor="w-field" className="field-label">{t("wiz.field")}</label>
                  <input
                    id="w-field"
                    className="input"
                    value={field}
                    aria-invalid={!!errors.field}
                    onChange={(e) => setField(e.target.value)}
                  />
                  {errors.field && <p className="mt-1 text-[11px] text-danger">{errors.field}</p>}
                </div>
                <div>
                  <label htmlFor="w-country" className="field-label">{t("wiz.country")}</label>
                  <select id="w-country" className="input" value={country} onChange={(e) => setCountry(e.target.value)}>
                    <option value="">{t("wiz.allCountries")}</option>
                    {countries.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <p className="mt-1.5 text-[11px] text-muted">{t("wiz.countryHint")}</p>
                </div>
              </>
            )}

            {step === 1 && (
              <>
                <div>
                  <label htmlFor="w-budget" className="field-label">{t("wiz.budget")}</label>
                  <input
                    id="w-budget"
                    type="number"
                    className="input figure"
                    value={budget}
                    min={1}
                    step={500}
                    aria-invalid={!!errors.budget}
                    onChange={(e) => setBudget(Number(e.target.value))}
                  />
                  {errors.budget && <p className="mt-1 text-[11px] text-danger">{errors.budget}</p>}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="w-bcur" className="field-label">{t("wiz.budgetCurrency")}</label>
                    <select id="w-bcur" className="input" value={budgetCurrency} onChange={(e) => setBudgetCurrency(e.target.value)}>
                      {currencies.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="w-rcur" className="field-label">{t("wiz.showIn")}</label>
                    <select id="w-rcur" className="input" value={reportCurrency} onChange={(e) => setReportCurrency(e.target.value)}>
                      {currencies.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </>
            )}

            {step === 2 && (
              <div role="radiogroup" aria-label="Lifestyle" className="space-y-2.5">
                {LIFESTYLES.map((l) => {
                  const active = lifestyle === l.id;
                  return (
                    <button
                      key={l.id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => setLifestyle(l.id)}
                      className={`w-full rounded-xl border p-4 text-left transition-all ${
                        active
                          ? "border-primary bg-primary-weak shadow-sm"
                          : "border-border bg-surface-2 hover:border-muted/40"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-semibold ${active ? "text-primary" : "text-foreground"}`}>
                          {t(l.labelKey)}
                        </span>
                        <span
                          className={`grid h-4 w-4 place-items-center rounded-full border ${
                            active ? "border-primary bg-primary" : "border-muted/50"
                          }`}
                        >
                          {active && <span className="h-1.5 w-1.5 rounded-full bg-primary-fg" />}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted">{t(l.blurbKey)}</p>
                    </button>
                  );
                })}
              </div>
            )}

            {step === 3 && (
              <>
                <p className="text-[11px] text-muted">
                  {t("wiz.elig.note")}
                </p>
                <TranscriptUpload onApply={(g) => setGpa(String(g))} />
                <div>
                  <label htmlFor="w-nat" className="field-label">{t("wiz.nationality")}</label>
                  <input
                    id="w-nat"
                    className="input"
                    placeholder="e.g. Azerbaijan"
                    value={nationality}
                    onChange={(e) => setNationality(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="w-gpa" className="field-label">{t("wiz.gpa")}</label>
                    <input
                      id="w-gpa"
                      type="number"
                      className="input figure"
                      placeholder="3.5"
                      min={0}
                      max={4}
                      step={0.1}
                      value={gpa}
                      aria-invalid={!!errors.gpa}
                      onChange={(e) => setGpa(e.target.value)}
                    />
                    {errors.gpa && <p className="mt-1 text-[11px] text-danger">{errors.gpa}</p>}
                  </div>
                  <div>
                    <label htmlFor="w-lang" className="field-label">{t("wiz.langTest")}</label>
                    <input
                      id="w-lang"
                      className="input"
                      placeholder="IELTS 7.0"
                      value={languageTest}
                      onChange={(e) => setLanguageTest(e.target.value)}
                    />
                  </div>
                </div>
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Footer nav */}
      <div className="flex items-center justify-between gap-3 border-t border-border bg-surface-2/40 px-5 py-4">
        <button
          type="button"
          onClick={() => go(-1)}
          disabled={step === 0}
          className="btn-ghost disabled:pointer-events-none disabled:opacity-40"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M19 12H5M11 18l-6-6 6-6" />
          </svg>
          {t("wiz.back")}
        </button>

        {isLast ? (
          <button type="button" onClick={submit} disabled={loading} className="btn-primary min-w-[150px]">
            {loading ? (
              <>
                <Spinner /> {t("wiz.planning")}
              </>
            ) : (
              <>
                {t("wiz.build")}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </>
            )}
          </button>
        ) : (
          <button type="button" onClick={() => go(1)} className="btn-primary min-w-[110px]">
            {t("wiz.next")}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4Z" />
    </svg>
  );
}
