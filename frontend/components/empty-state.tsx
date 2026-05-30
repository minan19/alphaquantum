"use client";

/**
 * OBS1: Genel-amaçlı boş durum bileşeni.
 *
 * Üç varyant:
 *   * default — sade boş ekran (icon + başlık + açıklama + CTA)
 *   * onboarding — yeni kullanıcıya "demo veriyi yükle" odaklı
 *   * empty-state-with-skeleton — yükleme sırasında shimmer kart
 */
import { motion } from "framer-motion";
import { type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";


export function EmptyState({
  icon: Icon,
  title,
  description,
  primaryAction,
  secondaryAction,
  className,
  variant = "default",
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  primaryAction?: { label: string; onClick: () => void; loading?: boolean };
  secondaryAction?: { label: string; onClick: () => void };
  className?: string;
  variant?: "default" | "compact";
}) {
  const compact = variant === "compact";
  return (
    <Card
      variant="glass"
      className={cn(
        "text-center",
        compact ? "p-6" : "p-10",
        className,
      )}
    >
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div
          className={cn(
            "mx-auto rounded-full grid place-items-center mb-3",
            "bg-aq-orbital/60 border border-aq-mist/40",
            compact ? "h-10 w-10" : "h-12 w-12",
          )}
        >
          <Icon
            className={cn(
              "text-aq-quantum-2",
              compact ? "h-5 w-5" : "h-6 w-6",
            )}
          />
        </div>
        <h3
          className={cn(
            "font-semibold text-foreground",
            compact ? "text-sm" : "text-base",
          )}
        >
          {title}
        </h3>
        {description && (
          <p
            className={cn(
              "mx-auto mt-1.5 text-aq-dust",
              compact ? "text-xs max-w-md" : "text-sm max-w-lg",
            )}
          >
            {description}
          </p>
        )}
        {(primaryAction || secondaryAction) && (
          <div className="flex items-center justify-center gap-2 mt-4">
            {primaryAction && (
              <Button
                onClick={primaryAction.onClick}
                disabled={primaryAction.loading}
                size={compact ? "sm" : "md"}
              >
                {primaryAction.label}
              </Button>
            )}
            {secondaryAction && (
              <Button
                variant="ghost"
                onClick={secondaryAction.onClick}
                size={compact ? "sm" : "md"}
              >
                {secondaryAction.label}
              </Button>
            )}
          </div>
        )}
      </motion.div>
    </Card>
  );
}
