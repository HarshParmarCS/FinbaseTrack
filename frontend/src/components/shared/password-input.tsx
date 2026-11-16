"use client";

import { Eye, EyeOff, Lock } from "lucide-react";
import { useState, type ComponentProps } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type PasswordInputProps = Omit<ComponentProps<"input">, "type">;

/**
 * A password field with a lock icon and a show/hide toggle. The toggle is a real button with
 * aria-pressed, so keyboard and screen-reader users can use it, and it does not steal focus from
 * the field. Works with React Hook Form's `register` (the ref is passed through).
 */
export function PasswordInput({ className, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const Toggle = visible ? EyeOff : Eye;
  return (
    <div className="relative">
      <Lock
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input type={visible ? "text" : "password"} className={cn("px-10", className)} {...props} />
      <button
        type="button"
        aria-label="Show password"
        aria-pressed={visible}
        aria-controls={props.id}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => setVisible((current) => !current)}
        className="absolute top-1/2 right-2 flex size-8 -translate-y-1/2 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition-colors outline-none hover:bg-brand-50 hover:text-brand-700 focus-visible:ring-4 focus-visible:ring-brand-200"
      >
        <Toggle className="size-4" aria-hidden />
      </button>
    </div>
  );
}
