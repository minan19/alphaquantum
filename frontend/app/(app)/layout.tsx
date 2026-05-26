"use client";

import { useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { CommandPalette } from "@/components/command-palette";
import { ProtectedRoute } from "@/components/protected-route";
import { Topbar } from "@/components/topbar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [cmdOpen, setCmdOpen] = useState(false);

  return (
    <ProtectedRoute>
      <div className="flex h-screen overflow-hidden">
        <Sidebar onOpenCommand={() => setCmdOpen(true)} />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Topbar onOpenCommand={() => setCmdOpen(true)} />
          <main id="main" className="flex-1 overflow-y-auto px-8 py-6">
            <div className="mx-auto max-w-7xl">{children}</div>
          </main>
        </div>
        <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
      </div>
    </ProtectedRoute>
  );
}
