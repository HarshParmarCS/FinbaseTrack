import { CheckCheck } from "lucide-react";
import Link from "next/link";
import { publicEnv } from "@/config/env";

export function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5 rounded-md outline-offset-4">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <CheckCheck className="size-4" aria-hidden />
      </span>
      <span className="text-[15px] font-semibold tracking-tight">
        {publicEnv.NEXT_PUBLIC_APP_NAME}
      </span>
    </Link>
  );
}
