import { Platform } from "react-native";

/**
 * 设计令牌：所有页面只从这里取颜色/字号/圆角，禁止在组件里散落魔法值。
 * 视觉基准来自 archive/legacy/jieqiu-app/index.html v3.1（暖白 + 深墨绿），但生产字号不低于 11px。
 */
export const colors = {
  bg: "#F5F4EF",
  bgElevated: "#FBFAF6",
  surface: "#FFFFFF",
  surfaceSunken: "#F1EFE8",
  ink: "#15211B",
  inkInverse: "#F3F6F2",
  muted: "#55615B",
  mutedInverse: "#A6B5AD",
  subtle: "#64706A",
  line: "#E9E7E0",
  lineStrong: "#DCD8CD",

  green: "#0E6B4F",
  greenPressed: "#0A5740",
  greenSoft: "#EAF3EE",
  greenSoftStrong: "#DDEDE4",
  greenDark: "#0A4F3C",
  greenAccent: "#9FE3C8",

  danger: "#A8443A",
  dangerPressed: "#8F352D",
  dangerSoft: "#F7E9E6",

  amber: "#8A5510",
  amberSoft: "#F7EFE1",
  amberLine: "#EBD9B8",

  heroTop: "#122B22",
  heroBottom: "#0A1813",
  heroLine: "rgba(159,227,200,0.18)",

  white: "#FFFFFF",
  black: "#000000",
  overlay: "rgba(8, 18, 13, 0.46)",
} as const;

export const gradients = {
  // 仅用于已发布预测主卡：同一墨绿色相内的明度变化，不做彩色渐变。
  verdict: [colors.heroTop, colors.heroBottom] as const,
} as const;

export const spacing = {
  xxs: 4,
  xs: 6,
  sm: 8,
  md: 12,
  base: 12,
  lg: 16,
  xl: 16,
  xxl: 20,
  x3: 20,
  x4: 24,
  x5: 28,
  x6: 32,
  x7: 40,
} as const;

export const radii = {
  sm: 10,
  md: 12,
  lg: 16,
  xl: 18,
  card: 16,
  hero: 24,
  sheet: 24,
  pill: 999,
} as const;

export const fontFamily = {
  regular: Platform.select({ ios: "PingFang SC", android: "sans-serif", default: "System" }),
  medium: Platform.select({
    ios: "PingFang SC",
    android: "sans-serif-medium",
    default: "System",
  }),
  mono: Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" }),
} as const;

/** 字号下限 11：设计稿里的 9.5px 标签在生产端统一抬到 11。 */
export const type = {
  display: { fontSize: 30, lineHeight: 36, fontWeight: "600" as const, letterSpacing: -0.5 },
  h1: { fontSize: 24, lineHeight: 31, fontWeight: "600" as const, letterSpacing: -0.3, fontVariant: ["tabular-nums"] as const },
  h2: { fontSize: 20, lineHeight: 27, fontWeight: "600" as const, letterSpacing: -0.3, fontVariant: ["tabular-nums"] as const },
  h3: { fontSize: 16, lineHeight: 23, fontWeight: "600" as const, fontVariant: ["tabular-nums"] as const },
  body: { fontSize: 14, lineHeight: 22, fontWeight: "400" as const },
  bodyStrong: { fontSize: 14, lineHeight: 22, fontWeight: "600" as const },
  small: { fontSize: 12, lineHeight: 19, fontWeight: "400" as const },
  smallStrong: { fontSize: 12, lineHeight: 19, fontWeight: "600" as const },
  caption: { fontSize: 11, lineHeight: 16, fontWeight: "400" as const },
  captionStrong: { fontSize: 11, lineHeight: 16, fontWeight: "600" as const },
  overline: {
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "600" as const,
    letterSpacing: 0.2,
  },
  metric: { fontSize: 28, lineHeight: 32, fontWeight: "600" as const, letterSpacing: -0.5, fontVariant: ["tabular-nums"] as const },
  mono: { fontSize: 11, lineHeight: 16, fontWeight: "400" as const, letterSpacing: 0.1, fontVariant: ["tabular-nums"] as const },
} as const;

export const shadows = {
  card: Platform.select({
    ios: {
      shadowColor: "#102018",
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.06,
      shadowRadius: 18,
    },
    android: { elevation: 2 },
    default: {},
  }),
  float: Platform.select({
    ios: {
      shadowColor: "#102018",
      shadowOffset: { width: 0, height: 12 },
      shadowOpacity: 0.16,
      shadowRadius: 28,
    },
    android: { elevation: 8 },
    default: {},
  }),
  header: Platform.select({
    ios: {
      shadowColor: "#102018",
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.04,
      shadowRadius: 2,
    },
    android: { elevation: 1 },
    default: {},
  }),
} as const;

export const layout = {
  maxWidth: 430,
  pagePadding: 20,
  headerHeight: 64,
  tabBarHeight: 56,
  composerHeight: 56,
  touch: 44,
  inputHeight: 48,
} as const;

/** 动效时长：统一在这里改，页面不写散落数字。 */
export const motion = {
  fast: 160,
  base: 220,
  sheet: 280,
  toast: 1800,
  mascot: 3400,
} as const;
