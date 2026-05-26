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
        // Primary — flagship CTA, gradient + glow
        primary: [
          "bg-gradient-to-br from-aq-quantum to-aq-quantum-2 text-white",
          "shadow-quantum hover:shadow-quantum-lg",
          "hover:from-aq-quantum-2 hover:to-aq-quantum",
          // Inner highlight
          "before:absolute before:inset-0 before:bg-gradient-to-b",
          "before:from-white/15 before:to-transparent before:pointer-events-none",
        ],
        // Secondary — subtle, glass
        secondary: [
          "glass glass-hover text-foreground",
        ],
        // Outline — minimal
        outline: [
          "border border-aq-mist/60 bg-transparent text-foreground",
          "hover:border-aq-quantum/60 hover:bg-aq-quantum/5",
        ],
        // Ghost — no surface until hover
        ghost: [
          "text-aq-dust hover:text-foreground hover:bg-aq-mist/40",
        ],
        // Destructive — danger zone
        destructive: [
          "bg-aq-fission text-white shadow-elevation-2",
          "hover:bg-aq-fission/90",
        ],
        // Link — text-only
        link: [
          "text-aq-quantum hover:text-aq-quantum-2 underline-offset-4 hover:underline",
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
