"use client";

import { RunProvider } from "@/lib/run-context";
import { ActionBar } from "./ActionBar";
import { Rail } from "./Rail";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <RunProvider>
      <Rail />
      <div className="min-h-screen pl-16">
        <main className="mx-auto max-w-6xl px-8 pb-28 pt-10">{children}</main>
      </div>
      <ActionBar />
    </RunProvider>
  );
}
