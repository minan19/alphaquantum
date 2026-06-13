/** @type {import('next').NextConfig} */

// Faz 6 + fix/wcag-badge-reference — Content-Security-Policy.
// Env-koşullu connect-src: dev'de localhost+127.0.0.1+ws/wss; prod'da yalnız
// 'self' + NEXT_PUBLIC_API_BASE_URL origin'i. Lokal dev konfigürasyonu prod'a
// SIZMAZ. PROD_API_ORIGIN env yoksa boş — segments dahil edilmez, 'self' kalır.
const IS_DEV = process.env.NODE_ENV !== "production";
const PROD_API_ORIGIN = (() => {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!raw) return "";
  try {
    return new URL(raw).origin;
  } catch {
    return "";
  }
})();

const CONNECT_SRC = [
  "'self'",
  ...(IS_DEV ? ["http://127.0.0.1:8000", "http://localhost:8000", "ws:", "wss:"] : []),
  ...(!IS_DEV && PROD_API_ORIGIN ? [PROD_API_ORIGIN] : []),
];

const CSP_DIRECTIVES = [
  "default-src 'self'",
  // Font dosyaları: kendi origin (upload bayts /api/fonts/<id>) + Google Static.
  "font-src 'self' https://fonts.gstatic.com data:",
  // Stylesheet: Google Fonts CSS URL + Next/inline.
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  // Script: Next HMR + inline payloadlar.
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  // Image: self + data: (icon) + blob: (önizleme).
  "img-src 'self' data: blob:",
  // Backend API çağrıları — env-koşullu (yukarıda inşa edildi).
  `connect-src ${CONNECT_SRC.join(" ")}`,
  // Iframe yalnız self (Faz 5 önizleme).
  "frame-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
];

const nextConfig = {
  reactStrictMode: true,
  // Build-time check ensures lint failures fail builds (CI-friendly)
  eslint: {
    ignoreDuringBuilds: false,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: CSP_DIRECTIVES.join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
