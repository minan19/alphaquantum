import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/components/theme-provider";
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" suppressHydrationWarning className={inter.variable}>
      <body className="min-h-screen relative font-display">
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
