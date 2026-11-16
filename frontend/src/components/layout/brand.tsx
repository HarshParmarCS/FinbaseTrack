import Link from "next/link";
import { publicEnv } from "@/config/env";
import { cn } from "@/lib/utils";

/**
 * The Finbase Workdesk mark: original artwork (not the Finbase logo) in the brand palette.
 * A rounded violet tile with a pink chevron rising out of a stack of three "task" lines.
 * Colors come from tokens through `fill-*` classes.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("size-8 shrink-0", className)}>
      <rect width="32" height="32" rx="9" className="fill-brand-700" />
      <rect x="8" y="17" width="16" height="2.6" rx="1.3" className="fill-primary-foreground" />
      <rect x="8" y="22" width="11" height="2.6" rx="1.3" className="fill-brand-300" />
      <path d="M9.5 13.2 16 7.5l6.5 5.7-2 2.1L16 11.4l-4.5 3.9z" className="fill-highlight-500" />
    </svg>
  );
}

type BrandProps = {
  /** "light" for dark backgrounds (the sign-in panel). */
  tone?: "default" | "light";
  href?: string;
};

export function Brand({ tone = "default", href = "/dashboard" }: BrandProps) {
  const [first, ...rest] = publicEnv.NEXT_PUBLIC_APP_NAME.split(" ");
  return (
    <Link
      href={href}
      aria-label={`${publicEnv.NEXT_PUBLIC_APP_NAME} home`}
      className="flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-4 focus-visible:ring-brand-200"
    >
      <BrandMark />
      <span
        className={cn(
          "text-base leading-none font-bold tracking-tight",
          tone === "light" ? "text-primary-foreground" : "text-brand-700",
        )}
      >
        {first}
        {rest.length ? (
          <span
            className={cn(
              "font-medium",
              tone === "light" ? "text-brand-200" : "text-highlight-600",
            )}
          >
            {" "}
            {rest.join(" ")}
          </span>
        ) : null}
      </span>
    </Link>
  );
}
