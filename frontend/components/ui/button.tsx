"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  // Base: layout, focus, transitions, disabled state
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md",
    "text-sm font-medium tracking-tight",
    "transition-all duration-300 ease-quantum",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    "disabled:pointer-events-none disabled:opacity-50",
    "active:scale-[0.98]",
    "[&_svg]:size-4 [&_svg]:shrink-0",
    "relative overflow-hidden",
  ],
  {
    variants: {
      variant: {
        // Primary — flagship CTA, modül cascade
        primary: [
          "bg-primary text-primary-foreground shadow-elevation-2",
          "hover:bg-primary/90",
          // Inner highlight (gradient ışıltı için)
          "before:absolute before:inset-0 before:bg-gradient-to-b",
          "before:from-white/10 before:to-transparent before:pointer-events-none",
        ],
        // Secondary — subtle, glass yüzeyi (token-bağlı)
        secondary: [
          "bg-secondary text-secondary-foreground border border-border/40",
          "hover:bg-secondary/80",
        ],
        // Outline — minimal, hover'da modül ringi
        outline: [
          "border border-input bg-transparent text-foreground",
          "hover:border-ring hover:bg-accent hover:text-accent-foreground",
        ],
        // Ghost — no surface until hover
        ghost: [
          "text-muted-foreground hover:text-accent-foreground hover:bg-accent",
        ],
        // Destructive — danger zone
        destructive: [
          "bg-destructive text-destructive-foreground shadow-elevation-2",
          "hover:bg-destructive/90",
        ],
        // Link — text-only, modül-bağlı primary
        link: [
          "text-primary hover:text-primary/80 underline-offset-4 hover:underline",
          "p-0 h-auto",
        ],
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-base",
        icon: "h-10 w-10",
        "icon-sm": "h-8 w-8",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      >
        {children}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
