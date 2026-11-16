import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { IconTile } from "@/components/shared/icon-tile";
import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
  /** Smaller padding, for use inside a card. */
  compact?: boolean;
};

export function EmptyState({ icon, title, description, action, compact = false }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl px-6 text-center",
        compact
          ? "border border-dashed border-brand-200 bg-brand-50/40 py-8"
          : "bg-card py-16 shadow-card",
      )}
    >
      <IconTile icon={icon} size={compact ? "md" : "lg"} className="mb-4" />
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
