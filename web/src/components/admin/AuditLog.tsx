"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/admin";
import { ApiError } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";

export function AuditLog({ adminKey }: { adminKey: string }) {
  const audit = useQuery({
    queryKey: ["admin", "audit"],
    queryFn: () => adminApi.auditLog(adminKey, 100),
  });

  if (audit.isLoading)
    return <p className="text-sm text-muted-foreground">Loading audit log…</p>;
  if (audit.isError)
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {audit.error instanceof ApiError
            ? audit.error.detail
            : "Failed to load the audit log."}
        </AlertDescription>
      </Alert>
    );

  const entries = audit.data ?? [];

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <caption className="sr-only">Audit log, most recent first</caption>
        <thead className="bg-muted/50 text-left text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Time</th>
            <th scope="col" className="px-3 py-2 font-medium">Actor</th>
            <th scope="col" className="px-3 py-2 font-medium">Action</th>
            <th scope="col" className="px-3 py-2 font-medium">Subject</th>
            <th scope="col" className="px-3 py-2 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} className="border-t align-top">
              <td className="whitespace-nowrap px-3 py-2 text-muted-foreground">
                {new Date(e.created_at).toLocaleString()}
              </td>
              <td className="px-3 py-2">{e.actor}</td>
              <td className="px-3 py-2 font-medium">{e.action}</td>
              <td className="px-3 py-2 font-mono text-xs">{e.subject ?? "—"}</td>
              <td className="px-3 py-2">{e.detail ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
