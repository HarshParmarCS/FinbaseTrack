import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";

type FormFieldProps = {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
};

/** A label, a control and its inline error. The control must set `id`, `aria-invalid` and `aria-describedby`. */
export function FormField({ id, label, error, hint, children }: FormFieldProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && !error ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** The ids a control should reference for `aria-describedby`. */
export function describedBy(id: string, { error, hint }: { error?: string; hint?: string }) {
  if (error) return `${id}-error`;
  return hint ? `${id}-hint` : undefined;
}
