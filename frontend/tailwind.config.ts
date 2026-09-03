import type { Config } from "tailwindcss";

/**
 * Palette + motion tokens — SPEC.md §9.5 "UX & motion direction".
 *
 * Surfaces and chrome are soft pastel "clay". Data and status are NOT pastel — outcome
 * colors below carry meaning and stay high-contrast. `blue` intentionally shadows
 * Tailwind's default blue; this project doesn't use the default scale.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F1EADB",
        surface: "#FBF7F0",
        "surface-sunk": "#ECE4D3",
        sage: { DEFAULT: "#8FB89E", deep: "#5E9E7E" },
        blue: { DEFAULT: "#9DBFC9", deep: "#6E9AA8" },
        peach: { DEFAULT: "#EEC0A0", deep: "#E8A87C" },
        ink: { DEFAULT: "#3B3A36", soft: "#6B6860" },
        // Semantic — outcome states. Do not render these in pastel.
        outcome: {
          recovered: "#4F9575",
          failed: "#C0705A",
          partial: "#D9A441",
          deferred: "#6E9AA8",
          suppressed: "#A79E8E",
          review: "#D68E63",
        },
      },
      borderRadius: {
        squircle: "24px",
        card: "20px",
      },
      boxShadow: {
        float: "0 10px 30px -12px rgba(60,55,45,.28)",
        "float-sm": "0 6px 18px -10px rgba(60,55,45,.24)",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      transitionTimingFunction: {
        // paired with framer-motion spring { stiffness: 180, damping: 22 } for layout moves
        "out-soft": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
