"use client";

/**
 * M2 — Generic detay sayfası başlığı.
 * Geri linki + başlık + meta + aksiyon grubu (düzenle / sil).
 */
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface ResourceDetailHeaderProps {
  backHref: string;
  backLabel?: string;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function ResourceDetailHeader({
  backHref,
  backLabel = "Listeye dön",
  title,
  subtitle,
  actions,
}: ResourceDetailHeaderProps) {
  return (
    <header className="space-y-3">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        {backLabel}
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{title}</h1>
          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

/** Boş durum: detay verisi bulunamadığında kullanılır. */
export function ResourceDetailNotFound({
  resourceLabel,
  backHref,
}: {
  resourceLabel: string;
  backHref: string;
}) {
  return (
    <div className="space-y-4 animate-fade-in">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Listeye dön
      </Link>
      <div className="rounded-md border border-border bg-card p-8 text-center text-sm text-muted-foreground">
        {resourceLabel} bulunamadı.
      </div>
    </div>
  );
}
