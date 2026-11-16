import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

/** A rounded-square tile with a name's initials, used for projects (people use Avatar). */
export function InitialsTile({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-brand-gradient text-sm font-semibold text-primary-foreground shadow-glow",
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
