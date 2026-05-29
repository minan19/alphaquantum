"use client";

/**
 * BZ1: Onboarding sayfası — yeni kullanıcı landing'i.
 *
 * /onboarding'e gelir, OnboardingWizard render edilir.
 * Tamamlanınca /dashboard'a yönlendirme.
 */
import { useRouter } from "next/navigation";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";

export default function OnboardingPage() {
  const router = useRouter();
  return (
    <div className="min-h-screen relative">
      <div className="mesh-bg" aria-hidden="true" />
      <main id="main" className="relative z-10">
        <OnboardingWizard onComplete={() => router.push("/dashboard")} />
      </main>
    </div>
  );
}
