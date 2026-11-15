import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { PageMeta } from "@/types/api";

type PaginationProps = {
  meta: PageMeta;
  onPageChange: (page: number) => void;
  disabled?: boolean;
};

export function Pagination({ meta, onPageChange, disabled = false }: PaginationProps) {
  if (meta.total_pages <= 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground" aria-live="polite">
        Page {meta.page} of {meta.total_pages} · {meta.total} in total
      </p>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(meta.page - 1)}
          disabled={disabled || meta.page <= 1}
        >
          <ChevronLeft aria-hidden />
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(meta.page + 1)}
          disabled={disabled || meta.page >= meta.total_pages}
        >
          Next
          <ChevronRight aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
