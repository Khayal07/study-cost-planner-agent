import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Study Cost Planning Agent",
  description:
    "Plan the total real cost of studying abroad — tuition, living, insurance, visa, transport and hidden costs — grounded in sourced data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">{children}</div>
      </body>
    </html>
  );
}
