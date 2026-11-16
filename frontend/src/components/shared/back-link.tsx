import { ArrowLeft } from "lucide-react";
import Link from "next/link";

/** The "back to the list" pill above detail pages. */
export function BackLink({ href, children }: { href: string; children: string }) {
  return (
    <Link
      href={href}
      className="mb-4 inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground transition-colors outline-none hover:border-brand-300 hover:text-brand-700 focus-visible:ring-4 focus-visible:ring-brand-200"
    >
      <ArrowLeft className="size-3.5 shrink-0" aria-hidden />
      <span className="truncate">{children}</span>
    </Link>
  );
}
