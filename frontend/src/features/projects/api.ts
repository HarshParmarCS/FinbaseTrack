import { api } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  Envelope,
  MemberCreate,
  MemberOut,
  PagedEnvelope,
  ProjectCreate,
  ProjectDetailOut,
  ProjectListParams,
  ProjectOut,
  ProjectUpdate,
} from "@/types/api";

export function listProjects(params: ProjectListParams, signal?: AbortSignal) {
  return api.get<PagedEnvelope<ProjectOut>>(endpoints.projects.list, { query: params, signal });
}

export async function getProject(projectId: string, signal?: AbortSignal) {
  const body = await api.get<Envelope<ProjectDetailOut>>(endpoints.projects.detail(projectId), {
    signal,
  });
  return body.data;
}

export async function createProject(input: ProjectCreate) {
  return (await api.post<Envelope<ProjectDetailOut>>(endpoints.projects.list, input)).data;
}

export async function updateProject(projectId: string, input: ProjectUpdate) {
  const body = await api.patch<Envelope<ProjectDetailOut>>(
    endpoints.projects.detail(projectId),
    input,
  );
  return body.data;
}

export function deleteProject(projectId: string) {
  return api.delete(endpoints.projects.detail(projectId));
}

export async function listMembers(projectId: string, signal?: AbortSignal) {
  const body = await api.get<Envelope<MemberOut[]>>(endpoints.projects.members(projectId), {
    signal,
  });
  return body.data;
}

export async function addMember(projectId: string, input: MemberCreate) {
  return (await api.post<Envelope<MemberOut>>(endpoints.projects.members(projectId), input)).data;
}

export function removeMember(projectId: string, userId: string) {
  return api.delete(endpoints.projects.member(projectId, userId));
}
