import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: { extend: { colors: { brand: { 50: "#eef7ff", 100: "#d9edff", 600: "#1769aa", 700: "#115487", 900: "#12324a" } } } },
  plugins: [],
} satisfies Config;
