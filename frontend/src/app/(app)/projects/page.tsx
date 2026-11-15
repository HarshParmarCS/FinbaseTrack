import type { Metadata } from "next";
import { Suspense } from "react";
import { ProjectsView } from "@/features/projects/projects-view";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  // useSearchParams (filters live in the URL) must sit inside a Suspense boundary.
  return (
    <Suspense>
      <ProjectsView />
    </Suspense>
  );
}
