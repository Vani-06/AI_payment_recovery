"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotionSafe } from "./motion";

/** Count-up number. Animates from the previous value to `value` on change (SPEC §9.5). */
export function Num({
  value,
  format,
  ms = 800,
}: {
  value: number;
  format: (n: number) => string;
  ms?: number;
}) {
  const reduced = useReducedMotionSafe();
  const [display, setDisplay] = useState(value);
  const from = useRef(value);

  useEffect(() => {
    if (reduced || from.current === value) {
      setDisplay(value);
      from.current = value;
      return;
    }
    const a = from.current;
    const b = value;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / ms);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(a + (b - a) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
      else from.current = b;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, reduced, ms]);

  return <>{format(display)}</>;
}
