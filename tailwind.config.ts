import type { Config } from "tailwindcss";

const config: Config = {
  future: {
    hoverOnlyWhenSupported: true,
  },
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        // WCAG AA & AAA compliant accessible tokens
        a11y: {
          focus: "#2563eb",
          "focus-dark": "#60a5fa",
          "high-contrast": "#0f172a",
          muted: "#475569",
          subtle: "#334155",
        },
      },
      fontFamily: {
        sans: [
          'var(--font-geist-sans)',
          'Pretendard Variable',
          'Pretendard',
          '-apple-system',
          'BlinkMacSystemFont',
          'system-ui',
          'Apple SD Gothic Neo',
          'Noto Sans KR',
          'Malgun Gothic',
          'sans-serif',
        ],
        mono: [
          'var(--font-geist-mono)',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
    },
  },
  plugins: [],
};
export default config;
