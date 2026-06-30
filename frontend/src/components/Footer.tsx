"use client";

import { useI18n } from "@/lib/i18n";

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="mt-20 border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-4 py-8 text-sm text-muted sm:flex-row sm:items-center sm:px-6">
        <p className="max-w-md leading-relaxed">{t("footer.text")}</p>
        <div className="flex items-center gap-4">
          <span className="chip bg-primary-weak text-primary">{t("footer.sourced")}</span>
          <span className="chip bg-accent-weak text-accent">{t("footer.estimate")}</span>
        </div>
      </div>
    </footer>
  );
}
