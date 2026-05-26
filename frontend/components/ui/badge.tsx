import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      tone: {
        neutral: "bg-aq-mist/60 text-aq-neutron",
        info:    "bg-aq-plasma/15 text-aq-plasma ring-1 ring-aq-plasma/30",
        success: "bg-aq-fusion/15 text-aq-fusion ring-1 ring-aq-fusion/30",
        warn:    "bg-aq-solar/15 text-aq-solar ring-1 ring-aq-solar/30",
        critical:"bg-aq-fission/15 text-aq-fission ring-1 ring-aq-fission/30",
        primary: "bg-aq-quantum/15 text-aq-quantum-2 ring-1 ring-aq-quantum/30",
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
