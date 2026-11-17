/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        rr: {
          50: "#fff1f5",
          100: "#ffe4ec",
          200: "#fecdd9",
          300: "#fda4bd",
          400: "#fb7199",
          500: "#f43f78",
          600: "#e11d60",
          700: "#be124e",
          800: "#9d1145",
          900: "#85123f",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.06), 0 8px 24px -12px rgba(15, 23, 42, 0.12)",
      },
    },
  },
  plugins: [],
};
