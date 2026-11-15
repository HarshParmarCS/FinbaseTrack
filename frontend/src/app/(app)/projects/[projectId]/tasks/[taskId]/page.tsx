import type { Metadata } from "next";
import { Suspense } from "react";
import { TaskDetailView } from "@/features/tasks/task-detail-view";

export const metadata: Metadata = { title: "Task" };

async function TaskContent({
  params,
}: {
  params: PageProps<"/projects/[projectId]/tasks/[taskId]">["params"];
}) {
  const { projectId, taskId } = await params;
  return <TaskDetailView projectId={projectId} taskId={taskId} />;
}

export default function TaskPage({ params }: PageProps<"/projects/[projectId]/tasks/[taskId]">) {
  return (
    <Suspense>
      <TaskContent params={params} />
    </Suspense>
  );
}
