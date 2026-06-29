// Hand-built iCalendar (.ics) export — no dependency. RFC 5545 essentials only:
// one all-day VEVENT per deadline, with a 7-day display reminder.

import type { ApplicationOut } from "./api";

/** Escape text for an ICS value (commas, semicolons, backslashes, newlines). */
function esc(text: string): string {
  return text
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n");
}

/** "2027-02-15" → "20270215" (DATE value). Returns null for unparseable input. */
function toDateValue(iso: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[1]}${m[2]}${m[3]}` : null;
}

/** Add one day to a YYYYMMDD string (for the exclusive DTEND of an all-day event). */
function nextDay(yyyymmdd: string): string {
  const y = +yyyymmdd.slice(0, 4);
  const mo = +yyyymmdd.slice(4, 6);
  const d = +yyyymmdd.slice(6, 8);
  const dt = new Date(Date.UTC(y, mo - 1, d + 1));
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getUTCFullYear()}${p(dt.getUTCMonth() + 1)}${p(dt.getUTCDate())}`;
}

function stamp(): string {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

/** Build an ICS document from the applications that have a deadline. */
export function buildIcs(apps: ApplicationOut[]): string {
  const dtstamp = stamp();
  const lines: string[] = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Study Cost Planner//Scholarship Deadlines//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
  ];

  for (const a of apps) {
    if (!a.deadline) continue;
    const start = toDateValue(a.deadline);
    if (!start) continue;
    const descParts = [
      a.provider ? `Provider: ${a.provider}` : null,
      a.university_name ? `University: ${a.university_name}` : null,
      a.estimated_value != null ? `Worth: ${Math.round(a.estimated_value)} ${a.currency ?? ""}/yr` : null,
      a.application_url ? `Apply: ${a.application_url}` : null,
    ].filter(Boolean) as string[];

    lines.push(
      "BEGIN:VEVENT",
      `UID:scp-app-${a.id}@study-cost-planner`,
      `DTSTAMP:${dtstamp}`,
      `DTSTART;VALUE=DATE:${start}`,
      `DTEND;VALUE=DATE:${nextDay(start)}`,
      `SUMMARY:${esc(`Apply: ${a.scholarship_name}`)}`,
    );
    if (descParts.length) lines.push(`DESCRIPTION:${esc(descParts.join("\n"))}`);
    if (a.application_url) lines.push(`URL:${esc(a.application_url)}`);
    lines.push(
      "BEGIN:VALARM",
      "TRIGGER:-P7D",
      "ACTION:DISPLAY",
      `DESCRIPTION:${esc(`Deadline in 7 days: ${a.scholarship_name}`)}`,
      "END:VALARM",
      "END:VEVENT",
    );
  }

  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}

/** Trigger a browser download of the applications' deadlines as a .ics file. */
export function downloadIcs(apps: ApplicationOut[], filename = "scholarship-deadlines.ics"): void {
  const blob = new Blob([buildIcs(apps)], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
