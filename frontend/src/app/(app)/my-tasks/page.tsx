import { ListChecks } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = { title: "My Tasks" };

export default function MyTasksPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="My Tasks" description="Tasks assigned to you across all projects." />
      <EmptyState
        icon={ListChecks}
        title="A combined list is not available yet"
        description="The backend can list tasks per project but not across projects, so this page has no data source yet. Your open assigned tasks are on the dashboard, and each project's task list can be filtered by assignee."
        action={
          <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>
            Go to the dashboard
          </Link>
        }
      />
    </div>
  );
}
