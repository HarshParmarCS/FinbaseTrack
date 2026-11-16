import type { LucideIcon } from "lucide-react";
import type { ComponentProps } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type InputWithIconProps = ComponentProps<"input"> & { icon: LucideIcon };

/** An input with a decorative leading icon (the reference's email and building fields). */
export function InputWithIcon({ icon: Icon, className, ...props }: InputWithIconProps) {
  return (
    <div className="relative">
      <Icon
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input className={cn("pl-10", className)} {...props} />
    </div>
  );
}
