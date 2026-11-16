import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-20 w-full rounded-xl border border-input bg-input-fill px-3.5 py-2.5 text-base transition-colors outline-none placeholder:text-muted-foreground hover:border-brand-200 focus-visible:border-brand-400 focus-visible:bg-card focus-visible:ring-4 focus-visible:ring-brand-100 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-4 aria-invalid:ring-danger-soft md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
