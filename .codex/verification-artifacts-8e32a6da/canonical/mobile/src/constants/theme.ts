export const colors = {
  background: "#F4F0E8",
  cream: "#F4F0E8",

  surface: "#FFFDFA",
  surfaceSoft: "#F8F4ED",

  navy: "#162033",
  text: "#162033",
  secondaryText: "#465066",

  red: "#852C21",
  redDark: "#6F241B",

  olive: "#6B7654",

  border: "#DDD6CA",
  borderStrong: "#C8BFB1",

  white: "#FFFFFF",
} as const;

export const typography = {
  display: {
    fontSize: 36,
    lineHeight: 44,
  },
  h1: {
    fontSize: 32,
    lineHeight: 40,
  },
  body: {
    fontSize: 16,
    lineHeight: 24,
  },
  small: {
    fontSize: 14,
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    lineHeight: 16,
  },
} as const;

export const radius = {
  small: 6,
  default: 8,
  card: 12,
  large: 16,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;
