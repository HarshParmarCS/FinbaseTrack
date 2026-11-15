import { History } from "lucide-react";
import type { Metadata } from "next";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";

export const metadata: Metadata = { title: "Activity" };

export default function ActivityPage() {
  return (
    <>
      <PageHeader title="Activity" description="A timeline of recent changes in your projects." />
      <EmptyState
        icon={History}
        title="No activity to show yet"
        description="Changes to projects, members and tasks will appear here once the app is connected to your account."
      />
    </>
  );
}
