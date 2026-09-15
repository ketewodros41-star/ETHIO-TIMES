import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10.5px] font-mono font-medium uppercase tracking-wider transition-colors",
  {
    variants: {
      variant: {
        default: "border border-white/[0.1] bg-ink-800/80 text-paper-300 backdrop-blur-xs",
        green: "border border-accent-green/30 bg-accent-green/10 text-accent-green shadow-xs",
        gold: "border border-accent-gold/30 bg-accent-gold/10 text-accent-gold shadow-xs",
        red: "border border-signal-red/30 bg-signal-red/10 text-signal-red shadow-xs",
        blue: "border border-accent-blue/30 bg-accent-blue/10 text-blue-400 shadow-xs",
        muted: "border border-white/[0.05] bg-ink-750/60 text-paper-400",
        outline: "border border-white/[0.14] text-paper-200 hover:border-white/[0.25]",
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

