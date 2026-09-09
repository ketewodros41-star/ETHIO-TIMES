import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-label",
  {
    variants: {
      variant: {
        default: "border border-ink-600 text-paper-300",
        green: "border border-accent-green/40 bg-accent-green/10 text-accent-green",
        gold: "border border-accent-gold/40 bg-accent-gold/10 text-accent-gold",
        red: "border border-signal-red/40 bg-signal-red/10 text-signal-red",
        muted: "bg-ink-700 text-paper-500",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
