import type { Metadata } from "next";
import { AccountView } from "@/features/settings/account-view";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return <AccountView />;
}
