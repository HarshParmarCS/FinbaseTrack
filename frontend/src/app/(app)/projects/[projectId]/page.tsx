import type { Metadata } from "next";
import { Suspense } from "react";
import { ProjectDetailView } from "@/features/projects/project-detail-view";

export const metadata: Metadata = { title: "Project" };

async function ProjectContent({
  params,
}: {
  params: PageProps<"/projects/[projectId]">["params"];
}) {
  const { projectId } = await params;
  return <ProjectDetailView projectId={projectId} />;
}

export default function ProjectPage({ params }: PageProps<"/projects/[projectId]">) {
  // `params` is request data, so it is read inside Suspense (Cache Components).
  return (
    <Suspense>
      <ProjectContent params={params} />
    </Suspense>
  );
}
