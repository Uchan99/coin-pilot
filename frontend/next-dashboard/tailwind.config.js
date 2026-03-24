/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    "./lib/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      /* ── Stitch "Deep Sea" 디자인 토큰 ── */
      colors: {
        // 표면 계층 (깊이별 순서)
        surface: {
          DEFAULT: "#071325",
          dim: "#071325",
          low: "#101c2e",
          container: "#142032",
          high: "#1f2a3d",
          highest: "#2a3548",
          bright: "#2e394d",
          variant: "#2a3548",
          tint: "#adc6ff",
        },
        // 주요 색상
        primary: {
          DEFAULT: "#adc6ff",
          container: "#4d8eff",
          fixed: "#d8e2ff",
          "fixed-dim": "#adc6ff",
        },
        secondary: {
          DEFAULT: "#b7c6ee",
          container: "#384668",
          fixed: "#d9e2ff",
          "fixed-dim": "#b7c6ee",
        },
        tertiary: {
          DEFAULT: "#4ae176",
          container: "#00a74b",
          fixed: "#6bff8f",
          "fixed-dim": "#4ae176",
        },
        error: {
          DEFAULT: "#ffb4ab",
          container: "#93000a",
        },
        outline: {
          DEFAULT: "#8c909f",
          variant: "#424754",
        },
        // on- 계열 (텍스트/아이콘)
        "on-surface": {
          DEFAULT: "#d7e3fc",
          variant: "#c2c6d6",
        },
        "on-primary": "#002e6a",
        "on-error": "#690005",
        inverse: {
          surface: "#d7e3fc",
          primary: "#005ac2",
          "on-surface": "#253144",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        full: "9999px",
      },
    },
  },
  plugins: [],
};
