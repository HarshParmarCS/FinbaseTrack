"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { activityKeys } from "@/features/activity/keys";
import { dashboardKeys } from "@/features/dashboard/keys";
import {
  addMember,
  createProject,
  deleteProject,
  getProject,
  listMembers,
  listProjects,
  removeMember,
  updateProject,
} from "@/features/projects/api";
import { projectKeys } from "@/features/projects/keys";
import { taskKeys } from "@/features/tasks/keys";
import type { MemberCreate, ProjectCreate, ProjectListParams, ProjectUpdate } from "@/types/api";

export function useProjects(params: ProjectListParams = {}) {
  return useQuery({
    queryKey: projectKeys.list(params),
    queryFn: ({ signal }) => listProjects(params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: projectKeys.detail(projectId),
    queryFn: ({ signal }) => getProject(projectId, signal),
  });
}

export function useProjectMembers(projectId: string) {
  return useQuery({
    queryKey: projectKeys.members(projectId),
    queryFn: ({ signal }) => listMembers(projectId, signal),
  });
}

/** Everything that shows project counts, statistics or the activity feed may have changed. */
function useInvalidateProjectData() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: projectKeys.all }),
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all }),
      queryClient.invalidateQueries({ queryKey: activityKeys.all }),
    ]);
}

export function useCreateProject() {
  const invalidate = useInvalidateProjectData();
  return useMutation({
    mutationFn: (input: ProjectCreate) => createProject(input),
    onSuccess: invalidate,
  });
}

export function useUpdateProject(projectId: string) {
  const invalidate = useInvalidateProjectData();
  return useMutation({
    mutationFn: (input: ProjectUpdate) => updateProject(projectId, input),
    onSuccess: invalidate,
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProjectData();
  return useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: async (_data, projectId) => {
      queryClient.removeQueries({ queryKey: projectKeys.detail(projectId) });
      queryClient.removeQueries({ queryKey: taskKeys.all });
      await invalidate();
    },
  });
}

export function useAddMember(projectId: string) {
  const invalidate = useInvalidateProjectData();
  return useMutation({
    mutationFn: (input: MemberCreate) => addMember(projectId, input),
    onSuccess: invalidate,
  });
}

export function useRemoveMember(projectId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProjectData();
  return useMutation({
    mutationFn: (userId: string) => removeMember(projectId, userId),
    // Removing a member also unassigns their tasks on the server.
    onSuccess: async () => {
      await Promise.all([invalidate(), queryClient.invalidateQueries({ queryKey: taskKeys.all })]);
    },
  });
}
