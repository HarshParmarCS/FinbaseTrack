"use client";

import { usePathname } from "next/navigation";
import { GlobalProgress } from "@/components/layout/global-progress";
import { MobileNav } from "@/components/layout/mobile-nav";
import { findNavItem } from "@/config/navigation";

export function Topbar() {
  const pathname = usePathname();
  const current = findNavItem(pathname);

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center gap-2 bg-background/80 px-4 backdrop-blur sm:px-6 lg:px-8">
      <MobileNav />
      <p className="text-sm font-semibold text-foreground">{current?.label ?? ""}</p>
      <GlobalProgress />
    </header>
  );
}
