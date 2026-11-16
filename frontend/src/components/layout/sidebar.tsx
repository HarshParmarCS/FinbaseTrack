import { Brand } from "@/components/layout/brand";
import { SidebarAccount } from "@/components/layout/sidebar-account";
import { SidebarNav } from "@/components/layout/sidebar-nav";

/** Sidebar content, shared by the desktop sidebar and the mobile sheet. */
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 px-4 py-5">
      <div className="px-1">
        <Brand />
      </div>
      <div className="space-y-2">
        <p className="px-3 text-[0.68rem] font-semibold tracking-[0.18em] text-muted-foreground uppercase">
          Workspace
        </p>
        <SidebarNav onNavigate={onNavigate} />
      </div>
      <div className="mt-auto">
        <SidebarAccount />
      </div>
    </div>
  );
}

export function Sidebar() {
  return <SidebarContent />;
}
