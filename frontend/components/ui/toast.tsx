"use client";

/**
 * M1 — Sonner sarmal. Tek standart toast API'si.
 *
 * Mevcut kodda `import { toast } from "sonner"` doğrudan kullanılıyordu;
 * artık `@/components/ui/toast`'tan re-export edilir. ToasterProvider'ı
 * layout'a koymak yerine zaten orada olan `Toaster`'ı tutar.
 */
import { toast as sonnerToast } from "sonner";

export type ToastType = "success" | "error" | "warning" | "info" | "default";

export interface ToastOptions {
  description?: string;
  duration?: number;
  action?: { label: string; onClick: () => void };
}

function call(type: ToastType, title: string, opts?: ToastOptions) {
  const fn =
    type === "success" ? sonnerToast.success
    : type === "error" ? sonnerToast.error
    : type === "warning" ? sonnerToast.warning
    : type === "info" ? sonnerToast.info
    : sonnerToast;
  return fn(title, {
    description: opts?.description,
    duration: opts?.duration ?? 4000,
    action: opts?.action,
  });
}

export const toast = {
  success: (title: string, opts?: ToastOptions) => call("success", title, opts),
  error:   (title: string, opts?: ToastOptions) => call("error", title, opts),
  warning: (title: string, opts?: ToastOptions) => call("warning", title, opts),
  info:    (title: string, opts?: ToastOptions) => call("info", title, opts),
  default: (title: string, opts?: ToastOptions) => call("default", title, opts),
};

export { Toaster } from "sonner";
