"use client";

import { usePathname } from "next/navigation";
import { AccountMenu } from "@/components/layout/account-menu";
import { MobileNav } from "@/components/layout/mobile-nav";
import { findNavItem } from "@/config/navigation";

export function Topbar() {
  const pathname = usePathname();
  const current = findNavItem(pathname);

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur sm:px-6">
      <MobileNav />
      <p className="text-sm font-medium">{current?.label ?? ""}</p>
      <div className="ml-auto">
        <AccountMenu />
      </div>
    </header>
  );
}
