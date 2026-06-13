import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { cookies, headers } from "next/headers";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeTokens } from "@/components/theme-tokens";
import { FontLoader } from "@/components/font-loader";
import { detectModuleFromPathname } from "@/lib/tokens";
import { isValidTheme, THEME_COOKIE, type Theme } from "@/lib/theme";
import { Toaster } from "sonner";

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: {
    default: "Alpha Quantum",
    template: "%s · Alpha Quantum",
  },
  description:
    "Çok şirketli yönetim ve KOBİ nakit akışı zekası. CorpOS + FinOS modülleri.",
  applicationName: "Alpha Quantum",
  authors: [{ name: "Alpha Quantum" }],
  keywords: ["holding", "KOBİ", "nakit akışı", "tahsilat", "CRM", "PatronOS", "FinOS"],
  metadataBase: new URL("https://alphaquantum.com.tr"),
  openGraph: {
    type: "website",
    locale: "tr_TR",
    siteName: "Alpha Quantum",
    title: "Alpha Quantum — CorpOS + FinOS",
    description: "Holdinginizi tek panelden yönetin, alacaklarınızı bilimle tahsil edin.",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: dark)",  color: "#020410" },
    { media: "(prefers-color-scheme: light)", color: "#FAFAFA" },
  ],
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Faz 2: SSR'da pathname'den modül kimliğini tespit et.
  // `middleware.ts` x-pathname header'ını set ediyor; default 'aq' (çatı).
  const h = await headers();
  const pathname = h.get("x-pathname") ?? "/";
  const dataModule = detectModuleFromPathname(pathname);

  // Faz 7: SSR'da çerezden temayı oku → NO-FLASH (ilk boyamada doğru tema).
  // Çerez yoksa varsayılan dark.
  const cookieStore = await cookies();
  const rawTheme = cookieStore.get(THEME_COOKIE)?.value;
  const theme: Theme = isValidTheme(rawTheme) ? rawTheme : "dark";

  return (
    <html
      lang="tr"
      suppressHydrationWarning
      className={`${inter.variable}${theme === "light" ? " light" : ""}`}
      // FLASH YOK: data-module + data-theme SSR'da set edilir; JS hidratasyonu beklenmez.
      data-module={dataModule}
      data-theme={theme}
    >
      <body className="min-h-screen relative font-display">
        {/*
          Faz 2: Design Token SSR enjeksiyonu.
          <body> içinde, globals.css'in <head> link'inden SONRA render edilir
          → kaynak sırası güvencesi. Asıl güvence specificity'dir:
          html[data-module] (0,1,1) > :root (0,1,0).

          Faz 6: FontLoader, ThemeTokens'tan SONRA. Default font seçilmişse
          --font-display zincirinin başına prepend eder; yüklenmezse zincir
          var(--font-inter) → system-ui'a düşer (fallback bozulmaz).
        */}
        <ThemeTokens />
        <FontLoader />
        <a href="#main" className="skip-link">İçeriğe geç</a>
        <ThemeProvider>
          <AuthProvider>
            <div className="relative z-10">{children}</div>
          </AuthProvider>
          <Toaster
            position="top-right"
            // B5: Tema sistem ile sync (light/dark/system tümü)
            theme="system"
            className="font-display"
            toastOptions={{
              classNames: {
                toast: "!bg-aq-orbital !border-aq-mist !text-aq-neutron",
              },
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
