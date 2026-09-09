import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-9 w-full rounded-card border border-ink-600 bg-ink-900 px-3 text-sm text-paper-50 placeholder:text-paper-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-green",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
