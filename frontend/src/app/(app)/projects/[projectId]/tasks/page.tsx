import type { Metadata } from "next";
import { Suspense } from "react";
import { TasksView } from "@/features/tasks/tasks-view";

export const metadata: Metadata = { title: "Tasks" };

async function TasksContent({
  params,
}: {
  params: PageProps<"/projects/[projectId]/tasks">["params"];
}) {
  const { projectId } = await params;
  return <TasksView projectId={projectId} />;
}

export default function TasksPage({ params }: PageProps<"/projects/[projectId]/tasks">) {
  // `params` and the filters in the URL are request data, so they are read inside Suspense.
  return (
    <Suspense>
      <TasksContent params={params} />
    </Suspense>
  );
}
