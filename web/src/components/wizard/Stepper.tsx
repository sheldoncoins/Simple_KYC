import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export const STEP_LABELS = ["Start", "Passport", "Liveness", "Result"] as const;

export function Stepper({ current }: { current: number }) {
  const pct = (current / (STEP_LABELS.length - 1)) * 100;
  return (
    <nav aria-label="Progress" className="mb-6">
      <div className="relative">
        {/* track + gradient fill (aligned to the dot centres, inset 1rem each side) */}
        <div
          className="absolute left-4 right-4 top-4 h-1 -translate-y-1/2 rounded-full bg-secondary"
          aria-hidden
        />
        <div
          className="absolute left-4 top-4 h-1 -translate-y-1/2 rounded-full bg-brand-gradient transition-[width] duration-500 ease-out"
          style={{ width: `calc((100% - 2rem) * ${pct / 100})` }}
          aria-hidden
        />
        <ol className="relative flex items-center justify-between">
          {STEP_LABELS.map((label, i) => {
            const done = i < current;
            const active = i === current;
            return (
              <li key={label} className="flex flex-col items-center gap-1.5">
                <span
                  aria-current={active ? "step" : undefined}
                  className={cn(
                    "flex size-8 items-center justify-center rounded-full border-2 bg-background text-sm font-semibold transition-all",
                    done && "border-transparent bg-brand-gradient text-white shadow-md shadow-primary/30",
                    active && "border-primary text-primary ring-4 ring-primary/15",
                    !done && !active && "border-input text-muted-foreground",
                  )}
                >
                  {done ? <Check className="size-4 animate-pop-in" aria-hidden /> : i + 1}
                </span>
                <span
                  className={cn(
                    "text-[11px]",
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
      </div>
    </nav>
  );
}
