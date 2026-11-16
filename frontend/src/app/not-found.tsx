import { Compass } from "lucide-react";
import Link from "next/link";
import { Brand } from "@/components/layout/brand";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col items-center justify-center gap-8 px-6">
      <Brand />
      <div className="w-full">
        <EmptyState
          icon={Compass}
          title="Page not found"
          description="The page you are looking for does not exist or has moved."
          action={
            <Button asChild>
              <Link href="/dashboard">Go to dashboard</Link>
            </Button>
          }
        />
      </div>
    </main>
  );
}
