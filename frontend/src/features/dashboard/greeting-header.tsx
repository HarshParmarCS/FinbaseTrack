import { CalendarDays } from "lucide-react";
import { QuickActions } from "@/features/dashboard/quick-actions";
import { firstName, formatLongDate, greetingFor } from "@/features/dashboard/format";

/** The dashboard's brand band: greeting, today's date and the quick "New" actions. */
export function GreetingHeader({ name, now }: { name: string; now: Date }) {
  const title = name
    ? `${greetingFor(now.getHours())}, ${firstName(name)}`
    : greetingFor(now.getHours());
  return (
    <section
      aria-label="Welcome"
      className="relative overflow-hidden rounded-3xl bg-brand-band px-6 py-7 text-primary-foreground shadow-glow sm:px-8 sm:py-9"
    >
      <div className="relative flex flex-wrap items-end justify-between gap-5">
        <div className="space-y-2">
          <p className="flex items-center gap-2 text-sm text-brand-100">
            <CalendarDays className="size-4" aria-hidden />
            {formatLongDate(now)}
          </p>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
          <p className="max-w-lg text-sm text-brand-100">
            Here is what is happening across your projects today.
          </p>
        </div>
        <QuickActions />
      </div>
    </section>
  );
}
