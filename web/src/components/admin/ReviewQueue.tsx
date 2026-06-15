"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { adminApi } from "@/lib/admin";
import { ApiError } from "@/lib/api";
import type { ReviewListItem } from "@/lib/schemas";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

const SIGNAL_KEYS = [
  "liveness_pass",
  "liveness_score",
  "face_match",
  "face_match_score",
  "dedup_outcome",
  "dedup_score",
] as const;

function format(value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return String(Math.round(value * 1000) / 1000);
  return String(value ?? "—");
}

export function ReviewQueue({ adminKey }: { adminKey: string }) {
  const qc = useQueryClient();
  const queue = useQuery({
    queryKey: ["admin", "review"],
    queryFn: () => adminApi.reviewQueue(adminKey),
  });

  const resolve = useMutation({
    mutationFn: ({
      itemId,
      resolution,
    }: {
      itemId: number;
      resolution: "approve" | "reject";
    }) => adminApi.resolveReview(adminKey, itemId, resolution, "console"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "review"] }),
  });

  if (queue.isLoading)
    return <p className="text-sm text-muted-foreground">Loading queue…</p>;
  if (queue.isError)
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {queue.error instanceof ApiError
            ? queue.error.detail
            : "Failed to load the review queue."}
        </AlertDescription>
      </Alert>
    );

  const items = queue.data ?? [];
  if (items.length === 0)
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Nothing in the review queue.
      </p>
    );

  return (
    <ul className="space-y-4">
      {items.map((item: ReviewListItem) => (
        <li key={item.item_id}>
          <Card>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Session {item.session_id}</span>
                  {item.country && <Badge variant="outline">{item.country}</Badge>}
                  <Badge variant="warning">{item.reason}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {new Date(item.created_at).toLocaleString()}
                  {item.risk_score !== null &&
                    ` · risk ${item.risk_score.toFixed(2)}`}
                </p>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                {SIGNAL_KEYS.filter((k) => k in item.signals).map((k) => (
                  <div key={k} className="flex justify-between gap-2">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="font-medium">{format(item.signals[k])}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex gap-3">
                <Button
                  size="sm"
                  disabled={resolve.isPending}
                  onClick={() =>
                    resolve.mutate({ itemId: item.item_id, resolution: "approve" })
                  }
                >
                  {resolve.isPending && (
                    <Loader2 className="animate-spin" aria-hidden />
                  )}
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={resolve.isPending}
                  onClick={() =>
                    resolve.mutate({ itemId: item.item_id, resolution: "reject" })
                  }
                >
                  Reject
                </Button>
              </div>
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}
