import type { Metadata } from "next";
import { Suspense } from "react";
import { MyTasksView } from "@/features/tasks/my-tasks-view";

export const metadata: Metadata = { title: "My Tasks" };

// Filters live in the URL (useSearchParams), which needs a Suspense boundary.
export default function MyTasksPage() {
  return (
    <Suspense>
      <MyTasksView />
    </Suspense>
  );
}
