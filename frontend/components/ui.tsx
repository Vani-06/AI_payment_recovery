import type { ReactNode } from "react";

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-card bg-surface p-6 shadow-float ${className}`}>{children}</div>;
}

export function Blob({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div
      aria-hidden
      style={style}
      className={`pointer-events-none absolute -z-10 rounded-full blur-3xl opacity-40 ${className}`}
    />
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-card bg-surface-sunk/60 ${className}`} />;
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div>
      <p className="text-xs text-ink-soft">{label}</p>
      <p className="tnum mt-1 text-2xl font-semibold text-ink">{value}</p>
      {sub != null && <p className="tnum mt-0.5 text-xs text-ink-soft">{sub}</p>}
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-6">
      <h1 className="text-xl font-semibold text-ink">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-ink-soft">{subtitle}</p>}
    </header>
  );
}

export function Placeholder({ phase }: { phase: string }) {
  return (
    <div className="rounded-card border border-dashed border-surface-sunk bg-surface/40 p-12 text-center text-sm text-ink-soft">
      Lands in Phase {phase}. The shell, navigation and run controls are wired — this screen
      renders its data next.
    </div>
  );
}
