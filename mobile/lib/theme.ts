export const colors = {
  light: {
    background: "#FFFFFF",
    surface: "#F5F5F5",
    text: "#1A1A1A",
    textSecondary: "#6B7280",
    border: "#E5E7EB",
    accent: "#1A1A1A",
    accentText: "#FFFFFF",
    error: "#EF4444",
    success: "#22C55E",
    skeleton: "#E5E7EB",
    badge: {
      depop: "#FF2300",
      ebay: "#E53238",
    },
  },
  dark: {
    background: "#0A0A0A",
    surface: "#1A1A1A",
    text: "#F5F5F5",
    textSecondary: "#9CA3AF",
    border: "#2D2D2D",
    accent: "#F5F5F5",
    accentText: "#0A0A0A",
    error: "#F87171",
    success: "#4ADE80",
    skeleton: "#2D2D2D",
    badge: {
      depop: "#FF2300",
      ebay: "#E53238",
    },
  },
};

export type ThemeColors = typeof colors.light;

export function getColors(scheme: "light" | "dark" | null | undefined): ThemeColors {
  return colors[scheme === "dark" ? "dark" : "light"];
}
