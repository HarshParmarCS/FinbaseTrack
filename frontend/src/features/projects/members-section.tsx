"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, UserMinus, UserPlus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { FormField, describedBy } from "@/components/shared/form-field";
import { Notice } from "@/components/shared/notice";
import { SectionCard } from "@/components/shared/section-card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { useAddMember, useRemoveMember } from "@/features/projects/hooks";
import { addMemberSchema, type AddMemberValues } from "@/features/projects/schemas";
import { getActionErrorMessage, getFieldErrors, isApiError } from "@/lib/api/errors";
import { formatDate, initials } from "@/lib/format";
import type { MemberOut, ProjectDetailOut } from "@/types/api";

type Props = { project: ProjectDetailOut; currentUserId: string | undefined };

function addMemberMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 404 && error.message === "User not found.") {
      return "No registered user has that email address. They need to create an account first.";
    }
    if (error.status === 409) return error.message;
  }
  return getActionErrorMessage(error);
}

function AddMemberForm({ projectId }: { projectId: string }) {
  const addMember = useAddMember(projectId);
  const [failure, setFailure] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<AddMemberValues>({
    resolver: zodResolver(addMemberSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFailure(null);
    try {
      const member = await addMember.mutateAsync({ email: values.email });
      reset();
      toast.success(`${member.user.name} was added to the project`);
    } catch (error) {
      const fieldMessage = getFieldErrors(error).email;
      if (fieldMessage) setError("email", { type: "server", message: fieldMessage });
      else setFailure(addMemberMessage(error));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate aria-label="Add member" className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
        <div className="flex-1">
          <FormField id="member-email" label="Add a member by email" error={errors.email?.message}>
            <Input
              id="member-email"
              type="email"
              autoComplete="off"
              placeholder="name@example.com"
              aria-invalid={Boolean(errors.email)}
              aria-describedby={describedBy("member-email", { error: errors.email?.message })}
              {...register("email")}
            />
          </FormField>
        </div>
        <Button type="submit" disabled={addMember.isPending} className="sm:mt-[1.625rem]">
          {addMember.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <UserPlus aria-hidden />
          )}
          Add member
        </Button>
      </div>
      {failure ? <Notice kind="error">{failure}</Notice> : null}
    </form>
  );
}

function MemberRow({
  member,
  isYou,
  canRemove,
  onRemove,
}: {
  member: MemberOut;
  isYou: boolean;
  canRemove: boolean;
  onRemove: (member: MemberOut) => void;
}) {
  return (
    <li className="flex items-center gap-3 py-3">
      <Avatar>
        <AvatarFallback>{initials(member.user.name)}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
          <span className="truncate">{member.user.name}</span>
          {isYou ? <Badge variant="outline">You</Badge> : null}
          {member.is_owner ? <Badge variant="secondary">Owner</Badge> : null}
        </p>
        <p className="truncate text-xs text-muted-foreground">{member.user.email}</p>
      </div>
      <p className="hidden text-xs text-muted-foreground sm:block">
        Joined {formatDate(member.joined_at)}
      </p>
      {canRemove ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onRemove(member)}
          aria-label={`Remove ${member.user.name}`}
        >
          <UserMinus aria-hidden />
          Remove
        </Button>
      ) : null}
    </li>
  );
}

export function MembersSection({ project, currentUserId }: Props) {
  const removeMember = useRemoveMember(project.id);
  const [removing, setRemoving] = useState<MemberOut | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  // The backend's answer for this user. It still refuses anyone it does not allow.
  const canManage = project.allowed_actions.includes("manage_members");

  async function confirmRemove() {
    if (!removing) return;
    setRemoveError(null);
    try {
      await removeMember.mutateAsync(removing.user.id);
      toast.success(`${removing.user.name} was removed from the project`);
      setRemoving(null);
    } catch (error) {
      setRemoveError(getActionErrorMessage(error));
    }
  }

  return (
    <SectionCard
      title="Members"
      description={`${project.members.length} ${project.members.length === 1 ? "person has" : "people have"} access to this project`}
    >
      {canManage ? <AddMemberForm projectId={project.id} /> : null}
      <ul className="divide-y" aria-label="Project members">
        {project.members.map((member) => (
          <MemberRow
            key={member.user.id}
            member={member}
            isYou={member.user.id === currentUserId}
            canRemove={canManage && !member.is_owner}
            onRemove={(target) => {
              setRemoveError(null);
              setRemoving(target);
            }}
          />
        ))}
      </ul>
      {removing ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => !open && setRemoving(null)}
          title={`Remove ${removing.user.name}?`}
          description="They lose access to this project immediately, and any tasks assigned to them become unassigned. Tasks they created stay."
          confirmLabel="Remove member"
          onConfirm={() => void confirmRemove()}
          isPending={removeMember.isPending}
          error={removeError}
        />
      ) : null}
    </SectionCard>
  );
}
