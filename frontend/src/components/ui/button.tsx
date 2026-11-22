import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-sky-400 to-cyan-300 text-slate-950 font-semibold shadow-[0_0_24px_rgba(56,189,248,0.22)] hover:from-sky-300 hover:to-cyan-200",
        secondary:
          "border border-white/[0.11] bg-white/[0.06] backdrop-blur-md text-zinc-100 hover:bg-white/[0.11] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]",
        outline:
          "border border-white/[0.12] bg-white/[0.02] backdrop-blur-md text-zinc-200 hover:bg-white/[0.08]",
        ghost: "text-zinc-300 hover:bg-white/[0.07] hover:text-white",
        destructive:
          "border border-rose-400/30 bg-rose-500/80 text-white backdrop-blur-md hover:bg-rose-500 shadow-[0_4px_16px_rgba(244,63,94,0.25)]",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-lg px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
