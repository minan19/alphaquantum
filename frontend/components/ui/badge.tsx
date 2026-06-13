import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      tone: {
        neutral: "bg-muted text-foreground",
        info:    "bg-info/15 text-info ring-1 ring-info/30",
        success: "bg-success/15 text-success ring-1 ring-success/30",
        warn:    "bg-warning/15 text-warning ring-1 ring-warning/30",
        critical:"bg-destructive/15 text-destructive ring-1 ring-destructive/30",
        primary: "bg-primary/15 text-primary ring-1 ring-primary/30",
      },
      withDot: {
        true: "before:content-[''] before:w-1.5 before:h-1.5 before:rounded-full before:bg-current before:shadow-[0_0_8px_currentColor]",
        false: "",
      },
    },
    defaultVariants: { tone: "neutral", withDot: false },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, withDot, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone, withDot, className }))} {...props} />;
}
