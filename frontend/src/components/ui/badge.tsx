import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-sky-500/40 bg-sky-500/15 text-sky-300",
        secondary: "border-zinc-700 bg-zinc-800 text-zinc-300",
        success: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
        warning: "border-amber-500/40 bg-amber-500/15 text-amber-300",
        danger: "border-rose-500/40 bg-rose-500/15 text-rose-300",
        purple: "border-violet-500/40 bg-violet-500/15 text-violet-300",
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
