import type { Config } from "tailwindcss";

// Palette mirrors docs/design-tokens.json (ETHIOTIMES brand DNA).
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0B0C0E",
          800: "#131519",
          700: "#1C1F24",
          600: "#262A31",
        },
        paper: {
          50: "#F7F6F2",
          300: "#C9C7BF",
          500: "#8A897F",
        },
        accent: {
          green: "#1FA35A",
          gold: "#D4A24E",
        },
        signal: {
          red: "#C2483B",
          amber: "#D4A24E",
          green: "#1FA35A",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        label: "0.08em",
      },
      borderRadius: {
        card: "8px",
      },
    },
  },
  plugins: [],
};

export default config;
