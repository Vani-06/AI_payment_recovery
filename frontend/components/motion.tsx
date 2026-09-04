"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

/** Shared spring for anything that moves position (SPEC §9.5). */
export const SPRING = { type: "spring", stiffness: 180, damping: 22 } as const;
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;

export function useReducedMotionSafe(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const on = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

/** Card enter transition — travel + scale normally, plain fade under reduced motion. */
export function cardEnter(reduced: boolean) {
  return reduced
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2 } }
    : {
        initial: { opacity: 0, y: 16, scale: 0.96 },
        animate: { opacity: 1, y: 0, scale: 1 },
        transition: SPRING,
      };
}

/** Subtle pointer parallax (px offset from viewport centre). Zero under reduced motion. */
export function useParallax(strength = 4): { x: number; y: number } {
  const reduced = useReducedMotionSafe();
  const [xy, setXY] = useState({ x: 0, y: 0 });
  useEffect(() => {
    if (reduced) return;
    const on = (e: PointerEvent) => {
      const cx = window.innerWidth / 2;
      const cy = window.innerHeight / 2;
      setXY({ x: ((e.clientX - cx) / cx) * strength, y: ((e.clientY - cy) / cy) * strength });
    };
    window.addEventListener("pointermove", on);
    return () => window.removeEventListener("pointermove", on);
  }, [reduced, strength]);
  return xy;
}

export function Stagger({
  children,
  gap = 0.05,
  className,
}: {
  children: React.ReactNode;
  gap?: number;
  className?: string;
}) {
  const reduced = useReducedMotionSafe();
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: reduced ? 0 : gap } } }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotionSafe();
  return (
    <motion.div
      className={className}
      variants={{
        hidden: reduced ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.96 },
        show: {
          opacity: 1,
          y: 0,
          scale: 1,
          transition: reduced ? { duration: 0.2 } : SPRING,
        },
      }}
    >
      {children}
    </motion.div>
  );
}
