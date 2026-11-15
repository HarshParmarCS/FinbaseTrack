import { PageHeader } from "@/components/shared/page-header";
import { QuickActions } from "@/features/dashboard/quick-actions";
import { firstName, formatLongDate, greetingFor } from "@/features/dashboard/format";

export function GreetingHeader({ name, now }: { name: string; now: Date }) {
  return (
    <PageHeader
      title={
        name ? `${greetingFor(now.getHours())}, ${firstName(name)}` : greetingFor(now.getHours())
      }
      description={formatLongDate(now)}
      actions={<QuickActions />}
    />
  );
}
