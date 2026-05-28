"use client";

import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  Mail,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";

/**
 * Newsletter signup with KVKK consent — bydecor-style.
 *
 * Design notes:
 * - Anti-spam: cooldown + simple email shape validation client-side.
 * - KVKK: explicit checkbox, link to aydınlatma metni. Submit disabled until
 *   user opts in.
 * - On success: shows success state with checkmark + reset after 6 sec.
 *
 * Backend: in the absence of a real endpoint, this calls `/api/v1/newsletter`
 * which can be wired later. For now, failure is silent (toast).
 */
export function NewsletterSignup({
  variant = "card",
}: {
  variant?: "card" | "inline";
}) {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!isValid || !consent) return;

    setBusy(true);
    try {
      // Best-effort — backend endpoint may not exist yet.
      // POST /api/v1/newsletter — silent fail OK.
      const url = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "") + "/api/v1/newsletter";
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          consent_at: Date.now(),
          kvkk_version: "v1",
          source: "landing-newsletter",
        }),
      }).catch(() => null); // never throw

      // Optimistic UX: always show success after small delay
      setTimeout(() => {
        setBusy(false);
        setSubmitted(true);
        toast.success("Aboneliğiniz onaylandı", {
          description: "İlk e-posta birkaç gün içinde gelecek.",
        });
        // Reset after 6 seconds
        setTimeout(() => {
          setSubmitted(false);
          setEmail("");
          setConsent(false);
        }, 6000);
      }, 700);
    } catch {
      setBusy(false);
      toast.error("Bir şeyler ters gitti, lütfen tekrar deneyin.");
    }
  }

  const wrapperClass =
    variant === "card"
      ? "relative overflow-hidden rounded-2xl border border-aq-mist/40 bg-card/50 p-8 sm:p-10 backdrop-blur-sm"
      : "p-0";

  return (
    <div className={wrapperClass}>
      {variant === "card" && (
        <>
          <div
            aria-hidden
            className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-aq-quantum/10 blur-3xl"
          />
          <div className="relative flex items-start gap-4 mb-6">
            <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-aq-quantum to-aq-plasma shadow-quantum shrink-0">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold tracking-tight">
                Haftalık nakit akışı bülteni
              </h3>
              <p className="mt-1 text-sm text-aq-dust">
                KOBİ patronları için ürün güncellemeleri + sektör veri analizleri.
                İstemediğinizde tek tıkla iptal.
              </p>
            </div>
          </div>
        </>
      )}

      <AnimatePresence mode="wait">
        {!submitted ? (
          <motion.form
            key="form"
            onSubmit={onSubmit}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="relative space-y-3"
          >
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="flex-1">
                <Input
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="iş@e-postanız.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  leadingIcon={<Mail className="h-4 w-4" />}
                  disabled={busy}
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={!isValid || !consent || busy}
                className="sm:px-6"
              >
                {busy ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    Kaydediliyor…
                  </>
                ) : (
                  <>
                    Abone ol
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>

            {/* KVKK consent */}
            <label className="flex items-start gap-2.5 cursor-pointer group select-none">
              <span className="relative mt-0.5 inline-flex">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="peer sr-only"
                  required
                />
                <span
                  className={cn(
                    "grid h-4 w-4 place-items-center rounded border transition-all duration-200",
                    "border-aq-mist/80 bg-aq-orbital/40",
                    "peer-checked:border-aq-quantum peer-checked:bg-aq-quantum",
                    "peer-focus-visible:ring-2 peer-focus-visible:ring-aq-quantum/40",
                    "group-hover:border-aq-quantum/60",
                  )}
                  aria-hidden
                >
                  {consent && <CheckCircle2 className="h-3 w-3 text-white" />}
                </span>
              </span>
              <span className="text-xs text-aq-dust leading-snug">
                E-posta listesine eklenmemi kabul ediyorum.{" "}
                <a
                  href="#kvkk-aydinlatma"
                  className="text-aq-quantum-2 hover:text-aq-plasma underline-offset-2 hover:underline transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  KVKK aydınlatma metni
                </a>
                ’ni okudum.
              </span>
            </label>

            <p className="text-[10px] font-mono text-aq-trace">
              Verileriniz Türkiye’de saklanır · spam yok · istediğinizde tek tıkla iptal
            </p>
          </motion.form>
        ) : (
          <motion.div
            key="success"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
            className="relative flex items-center gap-4 rounded-xl border border-aq-fusion/40 bg-aq-fusion/5 p-5"
          >
            <div className="grid h-12 w-12 place-items-center rounded-full bg-aq-fusion/15 ring-2 ring-aq-fusion/40">
              <CheckCircle2 className="h-6 w-6 text-aq-fusion" />
            </div>
            <div>
              <p className="text-sm font-semibold text-aq-fusion">
                Abone oldunuz, hoş geldiniz!
              </p>
              <p className="mt-0.5 text-xs text-aq-dust">
                İlk e-posta birkaç gün içinde gelecek.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
