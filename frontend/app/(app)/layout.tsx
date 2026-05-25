"use client";

import { Sidebar } from "@/components/sidebar";
import { ProtectedRoute } from "@/components/protected-route";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
    </ProtectedRoute>
  );
}
