import { FolderKanban } from "lucide-react";
import type { Metadata } from "next";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return (
    <>
      <PageHeader title="Projects" description="Every project you own or belong to." />
      <EmptyState
        icon={FolderKanban}
        title="No projects to show yet"
        description="Your projects will appear here once the app is connected to your account."
      />
    </>
  );
}
