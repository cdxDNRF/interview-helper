import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border backdrop-blur-md px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-sky-400/35 bg-sky-400/15 text-sky-200",
        secondary: "border-white/[0.11] bg-white/[0.06] text-zinc-200",
        success: "border-emerald-400/35 bg-emerald-400/15 text-emerald-200",
        warning: "border-amber-400/35 bg-amber-400/15 text-amber-200",
        danger: "border-rose-400/35 bg-rose-400/15 text-rose-200",
        purple: "border-violet-400/35 bg-violet-400/15 text-violet-200",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
