import type { Metadata } from "next";
import { AdminConsole } from "@/components/admin/AdminConsole";

export const metadata: Metadata = {
  title: "Review console",
  robots: { index: false, follow: false },
};

export default function AdminPage() {
  return <AdminConsole />;
}
