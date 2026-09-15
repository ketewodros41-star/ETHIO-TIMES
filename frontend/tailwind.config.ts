import type { Config } from "tailwindcss";

// Palette mirrors docs/design-tokens.json (ETHIOTIMES brand DNA).
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07080A",
          900: "#0B0D11",
          850: "#101318",
          800: "#151820",
          750: "#1C202B",
          700: "#242A38",
          600: "#2F3748",
          500: "#3D465C",
        },
        paper: {
          50: "#F9F9F7",
          100: "#EFEFEA",
          200: "#DFDED7",
          300: "#C6C4BA",
          400: "#A4A093",
          500: "#817D70",
          600: "#605C51",
        },
        accent: {
          green: "#1FA35A",
          "green-hover": "#27BD6A",
          gold: "#D4A24E",
          "gold-hover": "#E5B360",
          blue: "#3B82F6",
        },
        signal: {
          red: "#E24436",
          amber: "#D4A24E",
          green: "#1FA35A",
          blue: "#3B82F6",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        poster: ["var(--font-poster)", "Impact", "sans-serif"],
      },
      letterSpacing: {
        label: "0.08em",
        editorial: "-0.015em",
      },
      borderRadius: {
        card: "10px",
        subtle: "6px",
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.3)",
        "card-hover": "0 8px 24px -4px rgba(0, 0, 0, 0.6), 0 2px 6px -1px rgba(0, 0, 0, 0.4)",
        "glow-green": "0 0 24px -4px rgba(31, 163, 90, 0.35)",
        "glow-red": "0 0 24px -4px rgba(226, 68, 54, 0.35)",
        "glow-gold": "0 0 24px -4px rgba(212, 162, 78, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
