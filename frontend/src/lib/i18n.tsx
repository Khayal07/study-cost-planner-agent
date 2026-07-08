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

  // Chat
  "chat.newChat": { en: "New chat", az: "Yeni söhbət" },
  "chat.delete": { en: "Delete conversation", az: "Söhbəti sil" },
  "chat.advisor": { en: "Study Abroad Advisor", az: "Xaricdə Təhsil Məsləhətçisi" },
  "chat.advisorSub": { en: "Remembers your plan · every figure is cited", az: "Planını yadda saxlayır · hər rəqəm sitatlıdır" },
  "chat.intro": {
    en: "Tell me your budget and where you'd like to study — I'll find universities that fit and explain every cost. Try:",
    az: "Büdcəni və harada oxumaq istədiyini de — uyğun universitetləri tapıb hər xərci izah edəcəyəm. Sına:",
  },
  "chat.placeholder": { en: "e.g. I want to study CS in Poland, budget €10,000", az: "məs. Polşada İT oxumaq istəyirəm, büdcə €10,000" },
  "chat.message": { en: "Message", az: "Mesaj" },
  "chat.send": { en: "Send message", az: "Mesaj göndər" },
  "chat.fits": { en: "Fits budget", az: "Büdcəyə uyğun" },
  "chat.over": { en: "Over", az: "Büdcədən çox" },
  "chat.explore": { en: "Explore", az: "Araşdır" },
  "chat.tuition": { en: "Tuition", az: "Təhsil haqqı" },
  "chat.living": { en: "Living", az: "Yaşayış" },
  "chat.free": { en: "free", az: "pulsuz" },
  "chat.perYear": { en: "/year", az: "/il" },
  "chat.perMo": { en: "/mo", az: "/ay" },
  "chat.aid": { en: "aid ~", az: "təqaüd ~" },
  "chat.breakdown": { en: "Annual breakdown · every figure cited", az: "İllik bölgü · hər rəqəm sitatlı" },
  "chat.matchTitle": { en: "Budget-fit match score", az: "Büdcə uyğunluq balı" },
  "chat.download": { en: "Download report", az: "Hesabatı yüklə" },
  "chat.preparing": { en: "Preparing…", az: "Hazırlanır…" },
  "chat.errReach": {
    en: "I couldn't reach the planning service. Please check the backend is running and try again.",
    az: "Planlama xidmətinə çıxa bilmədim. Backend işlədiyini yoxla və yenidən cəhd et.",
  },
  "chat.errPdf": {
    en: "I couldn't generate the PDF just now. Please try again in a moment.",
    az: "PDF yarada bilmədim. Bir az sonra yenidən cəhd et.",
  },

  // Applications
  "app.st.planned": { en: "Planned", az: "Planlanıb" },
  "app.st.in_progress": { en: "In progress", az: "Davam edir" },
  "app.st.submitted": { en: "Submitted", az: "Göndərilib" },
  "app.st.accepted": { en: "Accepted", az: "Qəbul olunub" },
  "app.st.rejected": { en: "Rejected", az: "Rədd edilib" },
  "app.signinTitle": { en: "Track your scholarship applications", az: "Təqaüd müraciətlərini izlə" },
  "app.signinBody": {
    en: "Sign in to save scholarships, manage deadlines and tick off documents as you go — all stored to your account.",
    az: "Təqaüdləri saxlamaq, son tarixləri idarə etmək və sənədləri işarələmək üçün daxil ol — hamısı hesabında saxlanır.",
  },
  "app.signinBtn": { en: "Sign in / Create account", az: "Daxil ol / Hesab yarat" },
  "app.errLoad": { en: "Couldn't load your applications.", az: "Müraciətlərini yükləyə bilmədik." },
  "app.errStatus": { en: "Couldn't update status.", az: "Statusu yeniləyə bilmədik." },
  "app.emptyTitle": { en: "No applications yet", az: "Hələ müraciət yoxdur" },
  "app.emptyBodyA": { en: "Build a plan, open a university's scholarships and tap", az: "Plan qur, universitetin təqaüdlərini aç və əlavə etmək üçün" },
  "app.emptyBodyB": { en: "to add one here.", az: "düyməsinə toxun." },
  "app.track": { en: "Track", az: "İzlə" },
  "app.heading": { en: "My applications", az: "Müraciətlərim" },
  "app.tracked": { en: "tracked", az: "izlənir" },
  "app.view": { en: "View", az: "Görünüş" },
  "app.view.list": { en: "list", az: "siyahı" },
  "app.view.calendar": { en: "calendar", az: "təqvim" },
  "app.export": { en: "Export .ics", az: ".ics yüklə" },
  "app.exportHas": { en: "Export deadlines as a calendar file (.ics)", az: "Son tarixləri təqvim faylı kimi yüklə (.ics)" },
  "app.exportNone": { en: "No deadlines to export yet", az: "Hələ ixrac üçün son tarix yoxdur" },
  "app.thisWeek": { en: "This week", az: "Bu həftə" },
  "app.submit": { en: "Submit", az: "Göndər" },
  "app.by": { en: "by", az: "—son tarix" },
  "app.daysLeft": { en: "days left", az: "gün qalıb" },
  "app.status": { en: "Application status", az: "Müraciət statusu" },
  "app.remove": { en: "Remove application", az: "Müraciəti sil" },
  "app.worth": { en: "Worth", az: "Dəyəri" },
  "app.deadline": { en: "Deadline", az: "Son tarix" },
  "app.overdue": { en: "overdue", az: "vaxtı keçib" },
  "app.dLeft": { en: "left", az: "qalıb" },
  "app.apply": { en: "Apply", az: "Müraciət et" },
  "app.documents": { en: "Documents", az: "Sənədlər" },
  "app.ready": { en: "ready", az: "hazır" },

  // Saved plans
  "saved.signinTitle": { en: "Sign in to save plans", az: "Planları saxlamaq üçün daxil ol" },
  "saved.signinBody": {
    en: "Save any cost plan and get a shareable link you can revisit or send to others.",
    az: "İstənilən xərc planını saxla və yenidən aça və ya başqalarına göndərə biləcəyin link al.",
  },
  "saved.signinBtn": { en: "Sign in", az: "Daxil ol" },
  "saved.emptyTitle": { en: "No saved plans yet", az: "Hələ saxlanan plan yoxdur" },
  "saved.emptyBodyA": { en: "Build a plan, then use", az: "Plan qur, sonra nəticələrdə" },
  "saved.emptyBodyB": { en: "on the results to keep it here.", az: "düyməsi ilə onu burada saxla." },
  "saved.shareAction": { en: "Save & share", az: "Saxla və paylaş" },
  "saved.heading": { en: "Saved plans", az: "Saxlanan planlar" },
  "saved.open": { en: "Open", az: "Aç" },
  "saved.copy": { en: "Copy link", az: "Linki kopyala" },
  "saved.copied": { en: "Copied!", az: "Kopyalandı!" },
  "saved.delete": { en: "Delete saved plan", az: "Saxlanan planı sil" },

  // Calendar
  "cal.today": { en: "Today", az: "Bu gün" },
  "cal.prev": { en: "Previous month", az: "Əvvəlki ay" },
  "cal.next": { en: "Next month", az: "Növbəti ay" },
  "cal.more": { en: "more", az: "daha" },
  "cal.none": {
    en: "None of your tracked applications has a deadline yet.",
    az: "İzlədiyin müraciətlərin heç birində son tarix yoxdur.",
  },

  // Cost categories (shared by Sankey / cash-flow / radar / forecast charts)
  "cost.tuition": { en: "Tuition", az: "Təhsil haqqı" },
  "cost.rent": { en: "Rent", az: "Kirayə" },
  "cost.food": { en: "Food & groceries", az: "Yemək və ərzaq" },
  "cost.transport": { en: "Transport", az: "Nəqliyyat" },
  "cost.insurance": { en: "Health insurance", az: "Tibbi sığorta" },
  "cost.visa": { en: "Visa / permit", az: "Viza / icazə" },
  "cost.utilities": { en: "Utilities & internet", az: "Kommunal və internet" },
  "cost.hidden_misc": { en: "Other fees", az: "Digər xərclər" },
  "cost.total": { en: "Total / year", az: "Cəmi / il" },

  // Sankey
  "sankey.title": { en: "Where the money goes", az: "Pul hara gedir" },
  "sankey.total": { en: "Annual total", az: "İllik cəm" },

  // Cash-flow
  "cashflow.title": { en: "Monthly cash flow", az: "Aylıq pul axını" },
  "cashflow.hint": {
    en: "Tuition shown as two installments per year; one-time costs land in month 1.",
    az: "Təhsil haqqı ildə iki hissə kimi göstərilir; birdəfəlik xərclər 1-ci aydadır.",
  },
  "cashflow.month": { en: "Month", az: "Ay" },
  "cashflow.cumulative": { en: "Cumulative spend", az: "Yığılmış xərc" },
  "cashflow.oneTime": { en: "One-time", az: "Birdəfəlik" },
  "cashflow.living": { en: "Living", az: "Yaşayış" },

  // Radar comparison
  "radar.title": { en: "Cost profile", az: "Xərc profili" },
  "radar.hint": {
    en: "Each axis is scaled to the most expensive option (100). Hover for real amounts.",
    az: "Hər ox ən bahalı varianta görə miqyaslanıb (100). Real məbləğ üçün üzərinə gəl.",
  },
  "radar.axis": { en: "Category", az: "Kateqoriya" },

  // Cost forecast
  "forecast.title": { en: "Cost forecast (next 4 years)", az: "Xərc proqnozu (növbəti 4 il)" },
  "forecast.hint": {
    en: "Projected with fixed inflation assumptions — a planning aid, not a promise.",
    az: "Sabit inflyasiya fərziyyələri ilə proqnoz — plan üçün bələdçidir, zəmanət deyil.",
  },
  "forecast.living": { en: "Living costs", az: "Yaşayış xərcləri" },
  "forecast.assumption": { en: "Assumption", az: "Fərziyyə" },
  "forecast.askAi": { en: "Get AI advice on this trend", az: "Bu trend üçün AI məsləhəti al" },
  "forecast.loading": { en: "Thinking…", az: "Düşünür…" },
  "forecast.noCommentary": {
    en: "AI advice is unavailable right now — the projection above still stands.",
    az: "AI məsləhəti hazırda mümkün deyil — yuxarıdakı proqnoz qüvvədədir.",
  },
  "forecast.aiDisclaimer": {
    en: "AI-generated advice — verify before relying on it.",
    az: "AI tərəfindən yaradılıb — istifadə etməzdən əvvəl yoxla.",
  },

  // Share card
  "share.title": { en: "Share card", az: "Paylaşım kartı" },
  "share.tagline": { en: "My study cost plan", az: "Mənim təhsil xərci planım" },
  "share.totalLabel": { en: "Total per year", az: "İllik cəmi" },
  "share.afterAid": { en: "After scholarships", az: "Təqaüddən sonra" },
  "share.download": { en: "Download PNG", az: "PNG yüklə" },
  "share.share": { en: "Share", az: "Paylaş" },
  "share.close": { en: "Close", az: "Bağla" },
  "share.footer": { en: "real costs, cited sources", az: "real xərclər, sitatlı mənbələr" },
};

// Localised month + weekday names for the deadline calendar.
export const MONTH_NAMES: Record<Locale, string[]> = {
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  az: ["Yanvar", "Fevral", "Mart", "Aprel", "May", "İyun", "İyul", "Avqust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"],
};
export const WEEKDAY_NAMES: Record<Locale, string[]> = {
  en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  az: ["B.e", "Ç.a", "Çər", "C.a", "Cüm", "Şən", "Baz"],
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
