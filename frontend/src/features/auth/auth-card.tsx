import type { ReactNode } from "react";

type AuthCardProps = {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
};

/** The form column of the split sign-in layout: heading, subtitle, form and a footer link. */
export function AuthCard({ title, description, children, footer }: AuthCardProps) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">{title}</h1>
        <p className="text-base text-muted-foreground">{description}</p>
      </div>
      {children}
      <p className="text-sm text-muted-foreground">{footer}</p>
    </div>
  );
}
