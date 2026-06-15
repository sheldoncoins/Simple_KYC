"use client";

import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AdminLogin } from "./AdminLogin";
import { ReviewQueue } from "./ReviewQueue";
import { MetricsDashboard } from "./MetricsDashboard";
import { AuditLog } from "./AuditLog";

const STORAGE_KEY = "kyc_admin_key";
const TABS = [
  { id: "queue", label: "Review queue" },
  { id: "metrics", label: "Metrics" },
  { id: "audit", label: "Audit log" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function AdminConsole() {
  const [adminKey, setAdminKey] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<TabId>("queue");

  // Hold the staff key in sessionStorage (cleared when the tab closes). A real
  // deployment would use SSO/short-lived cookies; this is a console scaffold.
  useEffect(() => {
    setAdminKey(sessionStorage.getItem(STORAGE_KEY));
    setReady(true);
  }, []);

  function signIn(key: string) {
    sessionStorage.setItem(STORAGE_KEY, key);
    setAdminKey(key);
  }
  function signOut() {
    sessionStorage.removeItem(STORAGE_KEY);
    setAdminKey(null);
  }

  if (!ready) return null;
  if (!adminKey)
    return (
      <main id="main" className="px-4">
        <AdminLogin onSubmit={signIn} />
      </main>
    );

  return (
    <main id="main" className="mx-auto w-full max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Review console</h1>
        <Button variant="outline" size="sm" onClick={signOut}>
          <LogOut aria-hidden />
          Sign out
        </Button>
      </div>

      <div role="tablist" aria-label="Console sections" className="mb-6 flex gap-1 border-b">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => setTab(t.id)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              tab === t.id
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "queue" && <ReviewQueue adminKey={adminKey} />}
        {tab === "metrics" && <MetricsDashboard adminKey={adminKey} />}
        {tab === "audit" && <AuditLog adminKey={adminKey} />}
      </div>
    </main>
  );
}
