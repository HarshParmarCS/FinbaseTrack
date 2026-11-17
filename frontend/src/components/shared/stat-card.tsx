import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { IconTile, type IconTileTone } from "@/components/shared/icon-tile";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type StatCardProps = {
  label: string;
  icon: LucideIcon;
  /** `undefined` means "not loaded": the card shows a dash, or a skeleton while loading. */
  value?: number | string;
  isLoading?: boolean;
  /** Small explanation under the value, for example what the number is out of. */
  hint?: string;
  tone?: IconTileTone;
  /** Makes the whole card a link to the page that lists what the number counts. */
  href?: string;
};

/** A KPI card in the style of the Finbase analytics mock: micro label, icon chip, big number. */
export function StatCard({
  label,
  icon,
  value,
  isLoading = false,
  hint,
  tone = "brand",
  href,
}: StatCardProps) {
  const card = (
    <Card size="sm" className="h-full transition-shadow hover:shadow-card-hover">
      <CardContent className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <p className="text-[0.7rem] font-semibold tracking-[0.12em] text-muted-foreground uppercase">
            {label}
          </p>
          {isLoading ? (
            <Skeleton className="h-8 w-14" />
          ) : (
            <p className="text-3xl font-semibold tracking-tight text-foreground tabular-nums">
              {value ?? "—"}
            </p>
          )}
          {hint && !isLoading ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        <IconTile icon={icon} tone={tone} size="sm" />
      </CardContent>
    </Card>
  );
  if (!href) return card;
  return (
    <Link
      href={href}
      className="block rounded-2xl outline-none focus-visible:ring-4 focus-visible:ring-brand-200"
    >
      {card}
    </Link>
  );
}
