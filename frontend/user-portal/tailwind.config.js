/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "../shared-ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--rp-font-sans)", "sans-serif"],
        mono: ["var(--rp-font-mono)", "monospace"],
      },
      colors: {
        canvas: "var(--rp-bg)",
        elevated: "var(--rp-bg-elevated)",
        ink: "var(--rp-text)",
        mute: "var(--rp-text-muted)",
        accent: "var(--rp-accent-strong)",
        line: "var(--rp-border)",
      },
    },
  },
  plugins: [],
};
