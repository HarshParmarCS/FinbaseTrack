"use client";

import { useState } from "react";
import { useAuth } from "@/features/auth/auth-provider";
import { ActivityCard } from "@/features/dashboard/activity-card";
import { utcToday } from "@/features/dashboard/format";
import { GreetingHeader } from "@/features/dashboard/greeting-header";
import { MyTasksCard } from "@/features/dashboard/my-tasks-card";
import { ProjectsOverviewCard } from "@/features/dashboard/projects-overview-card";
import { StatsGrid } from "@/features/dashboard/stats-grid";
import { StatusDistributionCard } from "@/features/dashboard/status-distribution-card";
import { UpcomingCard } from "@/features/dashboard/upcoming-card";

export function DashboardView() {
  const { user } = useAuth();
  const [now] = useState(() => new Date());
  const today = utcToday(now);

  return (
    <div className="space-y-6">
      <GreetingHeader name={user?.name ?? ""} now={now} />
      <StatsGrid />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <MyTasksCard today={today} />
          <ProjectsOverviewCard />
        </div>
        <div className="space-y-6">
          <StatusDistributionCard />
          <UpcomingCard today={today} />
          <ActivityCard now={now} />
        </div>
      </div>
    </div>
  );
}
