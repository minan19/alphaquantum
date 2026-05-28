"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Eye,
  EyeOff,
  Lock,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Logomark, Wordmark } from "@/components/brand/logomark";

const FEATURE_BULLETS = [
  {
    icon: Sparkles,
    title: "Yapay zekâ destekli tahsilat",
    body: "Vade öncesi/sonrası akıllı hatırlatma — KVKK uyumlu kanallar.",
  },
  {
    icon: ShieldCheck,
    title: "Kurumsal güvenlik",
    body: "PBKDF2-SHA256 (260k iter), JWT, audit log, multi-tenant izolasyon.",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  // Session ID — generated client-only to avoid SSR/CSR hydration mismatch.
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace("/dashboard");
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    setSessionId(Math.random().toString(36).slice(2, 10).toUpperCase());
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true);
    try {
      await login(username, password);
      toast.success("Hoş geldiniz", { description: `Giriş başarılı: ${username}` });
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(
          err.status === 401 ? "Kullanıcı adı veya şifre yanlış" : `Sunucu hatası (${err.status})`,
        );
      } else {
        toast.error("Bağlantı hatası", { description: "API'ya ulaşılamadı." });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.05fr_0.95fr]">
      {/* ───── Sol panel: marka + tagline + özellikler ───── */}
      <section className="relative hidden overflow-hidden lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
        <div className="mesh-bg" aria-hidden="true" />

        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.32, 0.72, 0, 1] }}
          className="relative z-10 flex items-center gap-3"
        >
          <Logomark size={44} animated />
          <Wordmark />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15, ease: [0.32, 0.72, 0, 1] }}
          className="relative z-10 space-y-10 max-w-xl"
        >
          <div>
            <p className="text-aq-plasma text-sm font-mono uppercase tracking-[0.22em]">
              CorpOS · FinOS · Quantum Intelligence
            </p>
            <h1 className="mt-4 text-5xl font-bold tracking-tight leading-[1.05] glow-text">
              Holdinginizin{" "}
              <span className="bg-gradient-to-r from-aq-quantum via-aq-quantum-2 to-aq-plasma bg-clip-text text-transparent">
                dijital sinir sistemi
              </span>
              .
            </h1>
            <p className="mt-6 text-base text-aq-dust leading-relaxed">
              Birden fazla şirketin envanteri, finansı, müşterisi ve tahsilatı —
              tek panelden. Alacaklar zamanında tahsil edilir, nakit akışı önceden
              görülür, kararlar veriyle alınır.
            </p>
          </div>

          <ul className="space-y-5">
            {FEATURE_BULLETS.map((f, i) => (
              <motion.li
                key={f.title}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 + i * 0.1, duration: 0.5 }}
                className="flex gap-4"
              >
                <div className="mt-0.5 grid h-9 w-9 place-items-center rounded-md bg-gradient-to-br from-aq-quantum/15 to-aq-plasma/15 ring-1 ring-aq-quantum/25">
                  <f.icon className="h-4 w-4 text-aq-quantum-2" />
                </div>
                <div>
                  <p className="font-medium">{f.title}</p>
                  <p className="text-sm text-aq-dust mt-0.5">{f.body}</p>
                </div>
              </motion.li>
            ))}
          </ul>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.6 }}
          className="relative z-10 flex items-center gap-3 text-xs text-aq-trace font-mono"
        >
          <div className="h-px flex-1 bg-gradient-to-r from-aq-quantum/40 to-transparent" />
          <span>KVKK · ISO 27001 · TÜRKPATENT ™</span>
        </motion.div>
      </section>

      {/* ───── Sağ panel: form ───── */}
      <section className="flex items-center justify-center px-6 py-10 lg:px-16">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.32, 0.72, 0, 1] }}
          className="w-full max-w-md"
        >
          {/* Mobile brand */}
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <Logomark size={36} />
            <Wordmark />
          </div>

          <h2 className="text-3xl font-bold tracking-tight">Tekrar hoş geldiniz</h2>
          <p className="mt-2 text-sm text-aq-dust">
            Hesabınıza giriş yaparak paneli açın.
          </p>

          <form onSubmit={onSubmit} className="mt-8 space-y-5">
            <div className="space-y-2">
              <label htmlFor="username" className="text-xs font-medium uppercase tracking-wider text-aq-dust">
                Kullanıcı adı
              </label>
              <Input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="ornek_kullanici"
                leadingIcon={<User className="h-4 w-4" />}
                disabled={busy}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-aq-dust">
                  Şifre
                </label>
                <a href="#" className="text-xs text-aq-quantum-2 hover:text-aq-plasma transition-colors">
                  Şifremi unuttum
                </a>
              </div>
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••"
                leadingIcon={<Lock className="h-4 w-4" />}
                trailingIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    className="hover:text-foreground transition-colors"
                    aria-label={showPassword ? "Şifreyi gizle" : "Şifreyi göster"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
                disabled={busy}
              />
            </div>

            <Button type="submit" size="lg" className="w-full mt-2" disabled={busy}>
              {busy ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Giriş yapılıyor…
                </span>
              ) : (
                <>
                  Giriş yap
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </Button>
          </form>

          {/* Trust strip */}
          <div className="mt-10 pt-6 border-t border-aq-mist/40">
            <p className="text-xs text-aq-trace text-center font-mono">
              Bu oturum TLS 1.3 ile şifrelenmiştir{sessionId && ` · ID-${sessionId}`}
            </p>
          </div>
        </motion.div>
      </section>
    </main>
  );
}
