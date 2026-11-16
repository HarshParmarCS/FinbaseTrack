import type { ReactNode } from "react";
import { Eyebrow } from "@/components/shared/eyebrow";
import { Card, CardContent } from "@/components/ui/card";

type SectionCardProps = {
  title: string;
  description?: string;
  /** Small pill label above the title. */
  eyebrow?: string;
  /** Right-aligned control in the header, such as a link. */
  action?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function SectionCard({
  title,
  description,
  eyebrow,
  action,
  children,
  className,
}: SectionCardProps) {
  return (
    <Card className={className}>
      <CardContent className="space-y-5">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            {eyebrow ? <Eyebrow className="mb-1">{eyebrow}</Eyebrow> : null}
            <h2 className="text-base font-semibold">{title}</h2>
            {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
          </div>
          {action}
        </div>
        {children}
      </CardContent>
    </Card>
  );
}
