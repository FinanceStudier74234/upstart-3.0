/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#0a0e17',
          panel: '#111827',
          border: '#1f2937',
          green: '#10b981',
          red: '#ef4444',
          amber: '#f59e0b',
          blue: '#3b82f6',
          cyan: '#06b6d4',
          purple: '#8b5cf6',
          text: '#e5e7eb',
          muted: '#6b7280',
        },
      },
    },
  },
  plugins: [],
}
