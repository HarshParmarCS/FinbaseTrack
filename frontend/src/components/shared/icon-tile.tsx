import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type IconTileTone = "brand" | "highlight" | "success" | "warning" | "danger" | "neutral";

const TONES: Record<IconTileTone, string> = {
  brand: "bg-brand-100 text-brand-700",
  highlight: "bg-highlight-50 text-highlight-600",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  neutral: "bg-muted text-muted-foreground",
};

const SIZES = {
  sm: "size-8 [&_svg]:size-4",
  md: "size-10 [&_svg]:size-5",
  lg: "size-12 [&_svg]:size-6",
} as const;

type IconTileProps = {
  icon: LucideIcon;
  tone?: IconTileTone;
  size?: keyof typeof SIZES;
  className?: string;
};

/** The reference's lavender circle with a line icon. Decorative: the icon is hidden from readers. */
export function IconTile({ icon: Icon, tone = "brand", size = "md", className }: IconTileProps) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full",
        TONES[tone],
        SIZES[size],
        className,
      )}
    >
      <Icon />
    </span>
  );
}
