import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export const STEP_LABELS = ["Start", "Passport", "Liveness", "Result"] as const;

export function Stepper({ current }: { current: number }) {
  return (
    <nav aria-label="Progress" className="mb-6">
      <ol className="flex items-center justify-between gap-2">
        {STEP_LABELS.map((label, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li key={label} className="flex flex-1 flex-col items-center gap-1.5">
              <span
                aria-current={active ? "step" : undefined}
                className={cn(
                  "flex size-8 items-center justify-center rounded-full border text-sm font-medium",
                  done && "border-primary bg-primary text-primary-foreground",
                  active && "border-primary text-primary",
                  !done && !active && "border-input text-muted-foreground",
                )}
              >
                {done ? <Check className="size-4" aria-hidden /> : i + 1}
              </span>
              <span
                className={cn(
                  "text-center text-xs",
                  active ? "font-medium text-foreground" : "text-muted-foreground",
                )}
              >
                {label}
                {active && <span className="sr-only"> (current step)</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
