/** @type {import('next').NextConfig} */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  // Clickjacking defence via CSP too (belt-and-braces with X-Frame-Options). We
  // deliberately do NOT constrain script-src/style-src here: Next.js injects inline
  // hydration scripts and the app ships inline theme/locale init scripts, so a
  // script-src policy would need nonces and could break rendering.
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
];

const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
