import type { LucideIcon } from "lucide-react";
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
};

export function StatCard({ label, icon: Icon, value, isLoading = false, hint }: StatCardProps) {
  return (
    <Card size="sm">
      <CardContent className="flex items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {isLoading ? (
            <Skeleton className="h-7 w-12" />
          ) : (
            <p className="text-2xl font-semibold tabular-nums">{value ?? "—"}</p>
          )}
          {hint && !isLoading ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        <div className="flex size-9 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <Icon className="size-4" aria-hidden />
        </div>
      </CardContent>
    </Card>
  );
}
