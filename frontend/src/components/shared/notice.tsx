import { Alert, AlertDescription } from "@/components/ui/alert";

/** A short result message under a form or list. Polite for successes, assertive for failures. */
export function Notice({ kind, children }: { kind: "success" | "error"; children: string }) {
  return (
    <Alert
      variant={kind === "error" ? "destructive" : "default"}
      role={kind === "error" ? "alert" : "status"}
    >
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}
