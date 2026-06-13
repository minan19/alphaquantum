import { cn } from "@/lib/cn";

/**
 * Skeleton — loading placeholder with shimmer animation.
 * Token-bağlı: bg-muted yüzeyi (modül-bağımsız), shimmer keyframe Tailwind config.
 */
export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-muted/40",
        "before:absolute before:inset-0",
        "before:-translate-x-full before:animate-shimmer",
        "before:bg-gradient-to-r before:from-transparent before:via-white/10 before:to-transparent",
        className,
      )}
      {...props}
    />
  );
}
