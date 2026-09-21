import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF8F3",
        panel: "#FFFFFF",
        ink: "#1C1B1A",
        muted: "#6B6558",
        line: "#DAD5C8",
        navy: {
          DEFAULT: "#1E3A5F",
          deep: "#122238",
          light: "#2C5282",
        },
        gold: "#B08D3F",
        brick: "#8C3B2E",
        ochre: "#A67C3D",
        forest: "#2F6B4F",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
