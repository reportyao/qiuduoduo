import { Appearance, Platform } from "react-native";

/**
 * 设计令牌：所有页面只从这里取颜色/字号/圆角，禁止在组件里散落魔法值。
 * 视觉基准来自 archive/legacy/jieqiu-app/index.html v3.1（暖白 + 深墨绿），但生产字号不低于 11px。
 *
 * 暗色模式：模块初始化时按系统深浅色一次性选定色板（同名 token 全量覆盖），
 * 全站模块级 StyleSheet 自动跟随；运行中切换系统主题需重启/刷新生效。
 * 暗色色板基于墨绿品牌（非纯黑），dark hero 比页面更深一档以保持主卡层次。
 */
const lightColors = {
  bg: "#F6F3EC",
  bgElevated: "#FCFAF5",
  surface: "#FFFEFB",
  surfaceSunken: "#EEEADF",
  ink: "#17221C",
  inkInverse: "#F4F6F1",
  muted: "#59655E",
  mutedInverse: "#B3C0B8",
  subtle: "#6C776F",
  line: "#E5E0D4",
  lineStrong: "#D6CFBF",

  green: "#0C6549",
  greenPressed: "#084D38",
  greenSoft: "#E7F0EA",
  greenSoftStrong: "#D7E8DE",
  greenDark: "#063E2E",
  greenAccent: "#A8E4C9",
  greenHighlight: "#8CD6B8",
  greenAccentSoft: "rgba(168,228,201,0.14)",
  onGreen: "#FFFFFF",

  danger: "#A8443A",
  dangerPressed: "#8F352D",
  dangerSoft: "#F7E9E6",
  dangerAccent: "#F2B8AE",
  dangerAccentLight: "#FFD3CC",

  amber: "#8C5A16",
  amberSoft: "#F6EEDD",
  amberLine: "#E4D2AF",
  amberAccent: "#FFD99B",

  heroTop: "#132920",
  heroBottom: "#08130E",
  heroLine: "rgba(168,228,201,0.20)",

  white: "#FFFFFF",
  black: "#000000",
  overlay: "rgba(8, 18, 13, 0.46)",
  whiteSoft: "rgba(255,255,255,0.08)",
  whiteOverlay10: "rgba(255,255,255,0.10)",
  whiteOverlay12: "rgba(255,255,255,0.12)",
  whiteOverlay15: "rgba(255,255,255,0.15)",
  whiteOverlay16: "rgba(255,255,255,0.16)",
  whiteOverlay22: "rgba(255,255,255,0.22)",
  whiteLine: "rgba(255,255,255,0.28)",
  lockCover: "rgba(255,255,255,0.94)",
  toastSuccessBg: "rgba(14,107,79,0.94)",
  toastWarningBg: "rgba(90,58,14,0.96)",
  toastErrorBg: "rgba(125,42,34,0.96)",
} as const;

const darkColors: Record<keyof typeof lightColors, string> = {
  bg: "#0D1A12",
  bgElevated: "#12241A",
  surface: "#13291F",
  surfaceSunken: "#0E2015",
  ink: "#E8EDE8",
  inkInverse: "#F4F6F1",
  muted: "#8AA094",
  mutedInverse: "#B3C0B8",
  subtle: "#7E9086",
  line: "#1E3D2C",
  lineStrong: "#2A4D38",

  green: "#34C28B",
  greenPressed: "#2AA776",
  greenSoft: "#12301F",
  greenSoftStrong: "#1A4029",
  greenDark: "#063E2E",
  greenAccent: "#A8E4C9",
  greenHighlight: "#8CD6B8",
  greenAccentSoft: "rgba(168,228,201,0.14)",
  onGreen: "#06231A",

  danger: "#D97C6F",
  dangerPressed: "#A85546",
  dangerSoft: "#2E1B18",
  dangerAccent: "#F2B8AE",
  dangerAccentLight: "#FFD3CC",

  amber: "#D9A75B",
  amberSoft: "#2B2416",
  amberLine: "#4A3D22",
  amberAccent: "#FFD99B",

  heroTop: "#051009",
  heroBottom: "#020805",
  heroLine: "rgba(168,228,201,0.20)",

  white: "#FFFFFF",
  black: "#000000",
  overlay: "rgba(0, 0, 0, 0.60)",
  whiteSoft: "rgba(255,255,255,0.08)",
  whiteOverlay10: "rgba(255,255,255,0.10)",
  whiteOverlay12: "rgba(255,255,255,0.12)",
  whiteOverlay15: "rgba(255,255,255,0.15)",
  whiteOverlay16: "rgba(255,255,255,0.16)",
  whiteOverlay22: "rgba(255,255,255,0.22)",
  whiteLine: "rgba(255,255,255,0.28)",
  lockCover: "rgba(255,255,255,0.96)",
  toastSuccessBg: "rgba(10,72,52,0.96)",
  toastWarningBg: "rgba(56,38,8,0.97)",
  toastErrorBg: "rgba(66,20,15,0.97)",
};

export const colorSchemeName: "light" | "dark" =
  Appearance.getColorScheme() === "dark" ? "dark" : "light";

export const colors: Readonly<Record<keyof typeof lightColors, string>> =
  colorSchemeName === "dark" ? darkColors : lightColors;

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
  md: 14,
  lg: 18,
  xl: 22,
  card: 20,
  hero: 26,
  sheet: 28,
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

/** 移动端阅读优先：正文 15、辅助 13、说明 12，杜绝 11px 正文。 */
export const type = {
  display: { fontSize: 34, lineHeight: 41, fontWeight: "600" as const, letterSpacing: -0.5 },
  h1: { fontSize: 28, lineHeight: 36, fontWeight: "600" as const, letterSpacing: -0.3, fontVariant: ["tabular-nums"] as const },
  h2: { fontSize: 23, lineHeight: 31, fontWeight: "600" as const, letterSpacing: -0.2, fontVariant: ["tabular-nums"] as const },
  h3: { fontSize: 18, lineHeight: 25, fontWeight: "600" as const, fontVariant: ["tabular-nums"] as const },
  body: { fontSize: 16, lineHeight: 24, fontWeight: "400" as const },
  bodyStrong: { fontSize: 16, lineHeight: 24, fontWeight: "600" as const },
  small: { fontSize: 14, lineHeight: 21, fontWeight: "400" as const },
  smallStrong: { fontSize: 14, lineHeight: 21, fontWeight: "600" as const },
  caption: { fontSize: 12, lineHeight: 18, fontWeight: "400" as const },
  captionStrong: { fontSize: 12, lineHeight: 18, fontWeight: "600" as const },
  overline: {
    fontSize: 12,
    lineHeight: 18,
    fontWeight: "600" as const,
    letterSpacing: 0.4,
  },
  metric: { fontSize: 34, lineHeight: 38, fontWeight: "600" as const, letterSpacing: -0.6, fontVariant: ["tabular-nums"] as const },
  mono: { fontSize: 12, lineHeight: 18, fontWeight: "400" as const, letterSpacing: 0.1, fontVariant: ["tabular-nums"] as const },
} as const;

export const shadows = {
  card: Platform.select({
    ios: {
      shadowColor: "#102018",
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.03,
      shadowRadius: 6,
    },
    android: { elevation: 0 },
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
  headerHeight: 68,
  tabBarHeight: 60,
  composerHeight: 60,
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
