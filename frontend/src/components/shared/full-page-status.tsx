import { Loader2, TriangleAlert } from "lucide-react";
import { IconTile } from "@/components/shared/icon-tile";
import { Button } from "@/components/ui/button";

export function FullPageLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-svh items-center justify-center gap-2 text-sm text-muted-foreground"
    >
      <Loader2 className="size-5 animate-spin text-brand-600" aria-hidden />
      {label}
    </div>
  );
}

export function FullPageError({
  title,
  description,
  onRetry,
}: {
  title: string;
  description: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex min-h-svh flex-col items-center justify-center gap-3 px-6 text-center"
    >
      <IconTile icon={TriangleAlert} tone="danger" size="lg" />
      <h1 className="text-xl font-bold tracking-tight">{title}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      <Button variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
