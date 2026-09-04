export const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
export const inrLakh = (n: number) => `₹${(n / 100000).toFixed(1)}L`;
export const inrShort = (n: number) =>
  n >= 100000 ? `₹${(n / 100000).toFixed(1)}L` : `₹${Math.round(n / 1000)}k`;
export const pct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`;
export const humanize = (s: string) => s.replace(/_/g, " ");
