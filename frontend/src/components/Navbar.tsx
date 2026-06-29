"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "@/lib/auth";

function AccountButton() {
  const { isAuthed, user, openAuth, logout } = useAuth();
  if (!isAuthed) {
    return (
      <button onClick={openAuth} className="btn-primary px-3 py-1.5 text-xs">
        Sign in
      </button>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <span className="hidden max-w-[140px] truncate text-xs text-muted sm:inline" title={user?.email}>
        {user?.email}
      </span>
      <button onClick={logout} className="btn-ghost px-2.5 py-1.5 text-xs">
        Sign out
      </button>
    </div>
  );
}

function Logo() {
  return (
    <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-fg shadow-sm">
      <svg width="20" height="20" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path d="M16 6 4 12l12 6 8-4v6h2v-7L16 6Z" fill="currentColor" />
        <path
          d="M9 16v4c0 1.7 3.1 3 7 3s7-1.3 7-3v-4l-7 3.5L9 16Z"
          fill="currentColor"
          opacity="0.55"
        />
      </svg>
    </span>
  );
}

export function Navbar() {
  const reduce = useReducedMotion();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.header
      initial={reduce ? false : { y: -64, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: reduce ? 0 : 0.4, ease: [0.16, 1, 0.3, 1] }}
      className={`sticky top-0 z-40 border-b glass transition-shadow duration-300 ${
        scrolled ? "border-border shadow-md" : "border-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <a href="/" className="flex items-center gap-2.5">
          <Logo />
          <span className="flex flex-col leading-none">
            <span className="font-display text-[15px] font-semibold tracking-tight">
              Study Cost Planner
            </span>
            <span className="mt-0.5 text-[11px] text-muted">
              total real cost, sourced
            </span>
          </span>
        </a>

        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted sm:inline-flex">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full" />
              <span className="inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
            Grounded in cited sources
          </span>
          <a
            href="https://github.com/Khayal07/study-cost-planner-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden h-9 w-9 place-items-center rounded-xl border border-border bg-surface text-foreground transition-colors hover:border-primary/40 hover:text-primary sm:grid"
            aria-label="View source on GitHub"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2A10 10 0 0 0 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.22.66-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.52 2.34 1.08 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.99 1.03-2.69-.1-.26-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02a9.6 9.6 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.38.1 2.64.64.7 1.03 1.6 1.03 2.69 0 3.84-2.34 4.69-4.57 4.94.36.31.68.92.68 1.85v2.74c0 .27.16.57.67.48A10 10 0 0 0 22 12 10 10 0 0 0 12 2Z" />
            </svg>
          </a>
          <AccountButton />
          <ThemeToggle />
        </div>
      </div>
    </motion.header>
  );
}
