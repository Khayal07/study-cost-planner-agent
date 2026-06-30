"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Locale = "en" | "az";
const STORAGE_KEY = "scp-locale";

// Lightweight UI dictionary. Covers the app chrome (nav, hero, tabs, wizard,
// footer); deep result/chat content stays in English for now. Add keys as needed.
const DICT: Record<string, { en: string; az: string }> = {
  // Navbar
  "nav.tagline": { en: "total real cost, sourced", az: "tam real xərc, mənbəli" },
  "nav.grounded": { en: "Grounded in cited sources", az: "Sitatlı mənbələrə əsaslanır" },
  "nav.signIn": { en: "Sign in", az: "Daxil ol" },
  "nav.signOut": { en: "Sign out", az: "Çıxış" },

  // Hero
  "hero.badge": { en: "AI study-cost intelligence", az: "Süni intellektlə təhsil xərci" },
  "hero.titleA": { en: "The", az: "Xaricdə təhsilin" },
  "hero.titleHighlight": { en: "real cost", az: "əsl qiyməti" },
  "hero.titleB": { en: "of studying abroad — not just tuition.", az: "— təkcə təhsil haqqı deyil." },
  "hero.subtitle": {
    en: "Tuition, living, insurance, visa, transport and the hidden fees nobody quotes you. Every figure is converted to your currency and traced to a cited source —",
    az: "Təhsil haqqı, yaşayış, sığorta, viza, nəqliyyat və heç kimin demədiyi gizli xərclər. Hər rəqəm valyutana çevrilir və sitatlı mənbəyə bağlanır —",
  },
  "hero.sourced": { en: "sourced", az: "mənbəli" },
  "hero.or": { en: "or", az: "və ya" },
  "hero.flagged": { en: "clearly flagged as an estimate", az: "açıq şəkildə təxmin kimi qeyd olunur" },
  "hero.countries": { en: "countries", az: "ölkə" },
  "hero.universities": { en: "universities", az: "universitet" },
  "hero.figures": { en: "cited figures", az: "sitatlı rəqəm" },

  // Tabs
  "tab.form": { en: "Budget form", az: "Büdcə formu" },
  "tab.form.hint": { en: "Structured inputs", az: "Strukturlu daxiletmə" },
  "tab.chat": { en: "Chat", az: "Söhbət" },
  "tab.chat.hint": { en: "Ask in plain language", az: "Sadə dillə soruş" },
  "tab.applications": { en: "Applications", az: "Müraciətlər" },
  "tab.applications.hint": { en: "Track scholarships", az: "Təqaüdləri izlə" },
  "tab.saved": { en: "Saved", az: "Saxlanan" },
  "tab.saved.hint": { en: "Your plans & links", az: "Planların və linklər" },

  // Wizard
  "wiz.title": { en: "Build a cost plan", az: "Xərc planı qur" },
  "wiz.step": { en: "Step", az: "Addım" },
  "wiz.s.study": { en: "Study", az: "Təhsil" },
  "wiz.s.budget": { en: "Budget", az: "Büdcə" },
  "wiz.s.lifestyle": { en: "Lifestyle", az: "Həyat tərzi" },
  "wiz.s.eligibility": { en: "Eligibility", az: "Uyğunluq" },
  "wiz.field": { en: "Field of study", az: "Təhsil sahəsi" },
  "wiz.country": { en: "Destination country", az: "Hədəf ölkə" },
  "wiz.allCountries": { en: "All countries", az: "Bütün ölkələr" },
  "wiz.countryHint": { en: "Leave on “All countries” to compare everywhere.", az: "Hər yeri müqayisə etmək üçün “Bütün ölkələr”də saxla." },
  "wiz.budget": { en: "Yearly budget", az: "İllik büdcə" },
  "wiz.budgetCurrency": { en: "Budget currency", az: "Büdcə valyutası" },
  "wiz.showIn": { en: "Show results in", az: "Nəticələri göstər" },
  "wiz.lf.frugal": { en: "Frugal", az: "Qənaətli" },
  "wiz.lf.frugal.blurb": { en: "Shared housing, cook at home, minimal extras", az: "Paylaşılan mənzil, evdə bişir, minimal əlavələr" },
  "wiz.lf.moderate": { en: "Moderate", az: "Orta" },
  "wiz.lf.moderate.blurb": { en: "Typical student spending and comfort", az: "Tipik tələbə xərci və rahatlığı" },
  "wiz.lf.comfortable": { en: "Comfortable", az: "Rahat" },
  "wiz.lf.comfortable.blurb": { en: "Private room, eating out, more buffer", az: "Şəxsi otaq, çöldə yemək, daha çox ehtiyat" },
  "wiz.elig.note": { en: "Optional — used only to estimate scholarships you may qualify for. Leave blank to skip.", az: "İstəyə bağlı — yalnız uyğun ola biləcəyin təqaüdləri təxmin etmək üçün. Boş burax, keç." },
  "wiz.nationality": { en: "Nationality", az: "Vətəndaşlıq" },
  "wiz.gpa": { en: "GPA (0–4)", az: "Orta bal (0–4)" },
  "wiz.langTest": { en: "Language test", az: "Dil imtahanı" },
  "wiz.back": { en: "Back", az: "Geri" },
  "wiz.next": { en: "Next", az: "İrəli" },
  "wiz.build": { en: "Build cost plan", az: "Xərc planını qur" },
  "wiz.planning": { en: "Planning…", az: "Planlanır…" },

  // Country map
  "map.title": { en: "Explore by country", az: "Ölkə üzrə araşdır" },
  "map.hint": { en: "Tap a highlighted country to start a plan there", az: "Plan başlamaq üçün işıqlı ölkəyə toxun" },
  "map.covered": { en: "covered", az: "əhatə olunub" },
  "map.legend.covered": { en: "covered", az: "əhatə olunub" },
  "map.legend.none": { en: "no data yet", az: "hələ data yoxdur" },

  // Footer
  "footer.text": {
    en: "Figures are curated approximations grounded in cited sources and may change. Verify each at its source before deciding.",
    az: "Rəqəmlər sitatlı mənbələrə əsaslanan təxminlərdir və dəyişə bilər. Qərar verməzdən əvvəl hər birini mənbəsində yoxla.",
  },
  "footer.sourced": { en: "teal = sourced", az: "yaşıl = mənbəli" },
  "footer.estimate": { en: "amber = estimate", az: "kəhrəba = təxmin" },
};

export const localeInitScript = `
(function(){
  try {
    var l = localStorage.getItem("${STORAGE_KEY}");
    if (l === "az" || l === "en") document.documentElement.lang = l;
  } catch (e) {}
})();
`;

type I18nCtx = { locale: Locale; setLocale: (l: Locale) => void; t: (key: string) => string };
const Ctx = createContext<I18nCtx | null>(null);

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "az" || saved === "en") setLocaleState(saved);
    } catch {
      /* ignore */
    }
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
    document.documentElement.lang = l;
  }, []);

  const t = useCallback(
    (key: string) => {
      const entry = DICT[key];
      return entry ? entry[locale] : key;
    },
    [locale],
  );

  return <Ctx.Provider value={{ locale, setLocale, t }}>{children}</Ctx.Provider>;
}

export function useI18n(): I18nCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n must be used within LocaleProvider");
  return ctx;
}
