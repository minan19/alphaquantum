"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

/**
 * Wraps any client-side page that requires authentication. If the user is
 * not logged in (no token in localStorage), bounces them to /login.
 * Shows a small placeholder while the token state rehydrates.
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-400">
        Yükleniyor…
      </div>
    );
  }
  return <>{children}</>;
}
