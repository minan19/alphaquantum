import * as React from "react";
import { cn } from "@/lib/cn";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, leadingIcon, trailingIcon, ...props }, ref) => {
    const padLeft = leadingIcon ? "pl-10" : "pl-3.5";
    const padRight = trailingIcon ? "pr-10" : "pr-3.5";
    return (
      <div className="relative">
        {leadingIcon && (
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
            {leadingIcon}
          </div>
        )}
        <input
          ref={ref}
          type={type}
          className={cn(
            "h-10 w-full rounded-md bg-background/60 text-sm text-foreground",
            "border border-input placeholder:text-muted-foreground",
            "transition-all duration-200 ease-quantum",
            "focus:bg-background/80 focus:border-ring focus:outline-none",
            "focus:ring-2 focus:ring-ring/30",
            "disabled:cursor-not-allowed disabled:opacity-50",
            padLeft, padRight,
            className,
          )}
          {...props}
        />
        {trailingIcon && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground">
            {trailingIcon}
          </div>
        )}
      </div>
    );
  },
);
Input.displayName = "Input";
