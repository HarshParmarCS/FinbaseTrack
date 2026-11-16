import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** The small grey pill label above a heading ("Capabilities", "Solutions" in the reference). */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}
