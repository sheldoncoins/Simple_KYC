import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

/** A small, reassuring privacy line. Used wherever the user shares sensitive
 * data (passport, camera, wallet). */
export function PrivacyNote({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "flex items-start gap-2 rounded-md bg-muted/60 p-3 text-xs text-muted-foreground",
        className,
      )}
    >
      <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
