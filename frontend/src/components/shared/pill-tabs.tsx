import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type PillTabProps = {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
};

/**
 * A rounded toggle pill: outlined, with the reference's magenta ring when active. It is a real
 * button with aria-pressed, so Enter and Space work and assistive technology reports the state.
 */
export function PillTab({ pressed, onClick, children }: PillTabProps) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-full border bg-card px-3.5 text-sm transition-all outline-none focus-visible:ring-4 focus-visible:ring-brand-200",
        pressed
          ? "border-highlight-ring font-semibold text-brand-700 ring-1 ring-highlight-ring"
          : "border-border text-muted-foreground hover:border-brand-300 hover:text-brand-700",
      )}
    >
      {children}
    </button>
  );
}

type PillTabsProps = { label: string; children: ReactNode; className?: string };

/** A labelled group of PillTab buttons. */
export function PillTabs({ label, children, className }: PillTabsProps) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn("flex flex-wrap items-center gap-2", className)}
    >
      <span className="mr-1 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
        {label}
      </span>
      {children}
    </div>
  );
}
