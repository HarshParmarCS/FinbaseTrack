import { ListChecks } from "lucide-react";
import type { Metadata } from "next";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";

export const metadata: Metadata = { title: "My Tasks" };

export default function MyTasksPage() {
  return (
    <>
      <PageHeader title="My Tasks" description="Tasks assigned to you across all projects." />
      <EmptyState
        icon={ListChecks}
        title="No tasks to show yet"
        description="Your assigned tasks will appear here once the app is connected to your account."
      />
    </>
  );
}
