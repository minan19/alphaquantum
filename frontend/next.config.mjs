/** @type {import('next').NextConfig} */

// Faz 6 — Content-Security-Policy.
// Daha önce CSP yoktu; minimal-açma yaklaşımı. Yalnız bu fazın gerektirdiği
// kadar genişletildi (font kaynakları). Diğer kategoriler 'self' + Next.js'in
// HMR/inline gerektirdiği yerlerde 'unsafe-inline' (dev/prod aynı; sıkılaştırma
// ileri fazda).
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
  // Backend API çağrıları (lokal dev için 127.0.0.1 + localhost — lib/api.ts
  // default'u 'http://localhost:8000', tarayıcı 'localhost' ile resolve eder).
  "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 ws: wss:",
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
