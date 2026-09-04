"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./icons";

export const NAV = [
  { href: "/", label: "Command Center", icon: "gauge" },
  { href: "/batch", label: "Batch Run", icon: "list" },
  { href: "/leak-graph", label: "Leak Graph", icon: "share" },
  { href: "/audit", label: "Audit Trail", icon: "scroll" },
  { href: "/compliance", label: "Compliance", icon: "shield" },
  { href: "/review", label: "Review", icon: "inbox" },
  { href: "/chat", label: "Chat", icon: "chat" },
] as const;

export function Rail() {
  const path = usePathname();
  return (
    <nav className="fixed left-0 top-0 z-20 flex h-full w-16 flex-col items-center gap-1 border-r border-surface-sunk bg-surface py-4">
      <div className="mb-3 select-none text-lg" title="Revenue Sherlock">
        🔍
      </div>
      {NAV.map((n) => {
        const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
        return (
          <Link
            key={n.href}
            href={n.href}
            title={n.label}
            aria-current={active ? "page" : undefined}
            className={`group relative flex h-11 w-11 items-center justify-center rounded-card transition-colors ${
              active ? "bg-sage/25 text-sage-deep" : "text-ink-soft hover:bg-surface-sunk"
            }`}
          >
            <Icon name={n.icon} />
            <span className="pointer-events-none absolute left-14 z-30 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xs text-surface opacity-0 shadow-float-sm transition-opacity group-hover:opacity-100">
              {n.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
