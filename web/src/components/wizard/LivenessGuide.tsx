import { ArrowLeft, ArrowRight, Eye, Smile } from "lucide-react";
import { cn } from "@/lib/utils";

/** Animated visual cue for the current liveness action, alongside the text
 * instruction. Animations pause under prefers-reduced-motion (see globals.css). */
export function LivenessGuide({ action }: { action: string | null }) {
  return (
    <div className="flex h-14 items-center justify-center gap-3" aria-hidden>
      {action === "turn_left" && (
        <>
          <ArrowLeft className="size-7 text-primary animate-nudge-left" />
          <FaceDot className="animate-nudge-left" />
        </>
      )}
      {action === "turn_right" && (
        <>
          <FaceDot className="animate-nudge-right" />
          <ArrowRight className="size-7 text-primary animate-nudge-right" />
        </>
      )}
      {action === "blink" && <Eye className="size-10 text-primary animate-blink" />}
      {action === "smile" && <Smile className="size-10 text-primary animate-bounce-soft" />}
    </div>
  );
}

function FaceDot({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex size-10 items-center justify-center rounded-full border-2 border-primary",
        className,
      )}
    >
      <div className="flex gap-1.5">
        <span className="size-1.5 rounded-full bg-primary" />
        <span className="size-1.5 rounded-full bg-primary" />
      </div>
    </div>
  );
}
