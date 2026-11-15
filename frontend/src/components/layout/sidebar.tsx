import { Brand } from "@/components/layout/brand";
import { SidebarNav } from "@/components/layout/sidebar-nav";

export function Sidebar() {
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-4">
      <div className="px-2.5">
        <Brand />
      </div>
      <SidebarNav />
    </div>
  );
}
