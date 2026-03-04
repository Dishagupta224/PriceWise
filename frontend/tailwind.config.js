/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#081018",
        panel: "#101c28",
        panelSoft: "#152635",
        line: "#22384a",
        accent: "#5fd1ff",
        accentWarm: "#f5b942",
        success: "#3dd68c",
        warning: "#f6c945",
        danger: "#ff6b81",
        muted: "#8ea6bc",
      },
      boxShadow: {
        panel: "0 18px 50px rgba(0, 0, 0, 0.35)",
      },
      backgroundImage: {
        "dashboard-grid":
          "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
      },
      fontFamily: {
        sans: ["Segoe UI", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
