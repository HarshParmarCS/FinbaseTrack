import { Settings } from "lucide-react";
import type { Metadata } from "next";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Manage your account and preferences." />
      <EmptyState
        icon={Settings}
        title="Settings are not available yet"
        description="Account and preference options will be added after authentication is implemented."
      />
    </>
  );
}
