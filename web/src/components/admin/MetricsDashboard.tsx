"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/admin";
import { ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

export function MetricsDashboard({ adminKey }: { adminKey: string }) {
  const metrics = useQuery({
    queryKey: ["admin", "metrics"],
    queryFn: () => adminApi.metrics(adminKey),
  });

  if (metrics.isLoading)
    return <p className="text-sm text-muted-foreground">Loading metrics…</p>;
  if (metrics.isError)
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {metrics.error instanceof ApiError
            ? metrics.error.detail
            : "Failed to load metrics."}
        </AlertDescription>
      </Alert>
    );

  const m = metrics.data!;
  const countries = Object.entries(m.per_country);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Total sessions" value={String(m.total_sessions)} />
        <Stat label="Approved" value={pct(m.rates.approve ?? 0)} />
        <Stat label="In review" value={pct(m.rates.review ?? 0)} />
        <Stat label="Rejected" value={pct(m.rates.reject ?? 0)} />
        <Stat label="Dedup hit rate" value={pct(m.dedup_hit_rate)} />
        <Stat label="Liveness pass rate" value={pct(m.liveness_pass_rate)} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Per country</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th scope="col" className="py-1 font-medium">Country</th>
                <th scope="col" className="py-1 text-right font-medium">Total</th>
                <th scope="col" className="py-1 text-right font-medium">Approve</th>
                <th scope="col" className="py-1 text-right font-medium">Review</th>
                <th scope="col" className="py-1 text-right font-medium">Reject</th>
              </tr>
            </thead>
            <tbody>
              {countries.map(([iso, c]) => (
                <tr key={iso} className="border-t">
                  <td className="py-1 font-medium">{iso}</td>
                  <td className="py-1 text-right tabular-nums">{c.total ?? 0}</td>
                  <td className="py-1 text-right tabular-nums">{c.approve ?? 0}</td>
                  <td className="py-1 text-right tabular-nums">{c.review ?? 0}</td>
                  <td className="py-1 text-right tabular-nums">{c.reject ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
