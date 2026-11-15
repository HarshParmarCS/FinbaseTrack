import Link from "next/link";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  describeActivity,
  fullTimestamp,
  timeOfDay,
  type Lookups,
  type Ref,
} from "@/features/activity/describe";
import { relativeTime } from "@/features/dashboard/format";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ActivityOut } from "@/types/api";

function RefText({ value }: { value: Ref }) {
  return value.href ? (
    <Link href={value.href} className="font-medium hover:underline">
      {value.label}
    </Link>
  ) : (
    <span className="font-medium">{value.label}</span>
  );
}

type Props = {
  entry: ActivityOut;
  lookups: Lookups;
  now: Date;
  /** Hide the project name (inside a project's own timeline). */
  hideProject?: boolean;
  /** "relative" (2 hours ago) or "time" (3:45 PM, used under a day heading). */
  timeStyle?: "relative" | "time";
};

/** One activity entry as a sentence: actor, action, subject, project and time. */
export function ActivityItem({
  entry,
  lookups,
  now,
  hideProject = false,
  timeStyle = "time",
}: Props) {
  const described = describeActivity(entry, lookups);
  const showProject = !hideProject && described.project;
  return (
    <div className="flex items-start gap-3">
      <Avatar size="sm" className="mt-0.5">
        <AvatarFallback className={cn(described.isYou && "bg-primary/10 text-primary")}>
          {initials(entry.user.name)}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 text-sm leading-6">
        <p className="break-words">
          <span className="font-medium">{described.actor}</span> {described.verb}
          {described.subject ? (
            <>
              {" "}
              <RefText value={described.subject} />
            </>
          ) : null}
          {described.detail ? <> {described.detail}</> : null}
          {showProject && described.project ? (
            <span className="text-muted-foreground">
              {" "}
              in <RefText value={described.project} />
            </span>
          ) : null}
        </p>
        <time
          dateTime={entry.created_at}
          title={fullTimestamp(entry.created_at)}
          className="text-xs text-muted-foreground"
        >
          {timeStyle === "relative"
            ? relativeTime(entry.created_at, now)
            : timeOfDay(entry.created_at)}
          <span className="sr-only">, {fullTimestamp(entry.created_at)}</span>
        </time>
      </div>
    </div>
  );
}
