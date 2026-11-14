import { Appearance, Platform } from "react-native";

/**
 * 设计令牌：所有页面只从这里取颜色/字号/圆角，禁止在组件里散落魔法值。
 *
 * 色彩语义（2026-11-14 全面改版，中国彩民心智）：
 * - 红 brand = 中/命中/通过/盈利/品牌主行动（"红中"，麻将红中心智）
 * - 黑 loss = 不中/回避/亏损/连败/高风险（"手气黑了"；暗色下灰化表示负向）
 * - 琥珀 amber = 等数据/走水/离线/会员金
 * - 红 danger = 删除/退出/表单错误/系统错误（破坏性与品牌同族，场景天然隔离）
 * - hero 深红黑渐变 + 金 accent（中奖金）
 *
 * 暗色模式：模块初始化时按系统深浅色一次性选定色板（同名 token 全量覆盖），
 * 全站模块级 StyleSheet 自动跟随；运行中切换系统主题需重启/刷新生效。
 * 暗色底为暖炭（非绿黑、非纯黑），dark hero 比页面更深一档保持主卡层次。
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

  // 红 = 中/品牌
  brand: "#B0362B",
  brandPressed: "#8A2820",
  brandSoft: "#F8E9E5",
  brandSoftStrong: "#F0D6CF",
  brandDeep: "#3D2A08",
  brandAccent: "#E3B25C",
  brandHighlight: "#D0A04C",
  brandAccentSoft: "rgba(227,178,92,0.16)",
  onBrand: "#FFFFFF",

  // 黑 = 不中/亏损/回避
  loss: "#26231F",
  lossSolid: "#33302C",
  lossPressed: "#211F1C",
  lossSoft: "#ECEAE5",
  lossAccent: "#565049",
  lossAccentLight: "#B5AFA6",

  // 红 = 删除/退出/表单错误（破坏性，与品牌同族）
  danger: "#B0362B",
  dangerSolid: "#B0362B",
  dangerPressed: "#8A2820",
  dangerSoft: "#F8E9E5",
  dangerAccent: "#F2B8AE",
  dangerAccentLight: "#FFD3CC",

  // 琥珀 = 等数据/走水/警示/会员金
  amber: "#8C5A16",
  amberSoft: "#F6EEDD",
  amberLine: "#E4D2AF",
  amberAccent: "#FFD99B",

  heroTop: "#29100B",
  heroBottom: "#120504",
  heroLine: "rgba(227,178,92,0.22)",

  white: "#FFFFFF",
  black: "#000000",
  overlay: "rgba(8, 18, 13, 0.46)",
  inkOverlay8: "rgba(23,34,28,0.08)",
  whiteSoft: "rgba(255,255,255,0.08)",
  whiteOverlay10: "rgba(255,255,255,0.10)",
  whiteOverlay12: "rgba(255,255,255,0.12)",
  whiteOverlay15: "rgba(255,255,255,0.15)",
  whiteOverlay16: "rgba(255,255,255,0.16)",
  whiteOverlay22: "rgba(255,255,255,0.22)",
  whiteLine: "rgba(255,255,255,0.28)",
  lockCover: "rgba(255,255,255,0.94)",
  toastSuccessBg: "rgba(176,54,43,0.95)",
  toastWarningBg: "rgba(90,58,14,0.96)",
  toastErrorBg: "rgba(30,27,24,0.96)",
} as const;

const darkColors: Record<keyof typeof lightColors, string> = {
  bg: "#171210",
  bgElevated: "#1E1814",
  surface: "#241D18",
  surfaceSunken: "#1A1410",
  ink: "#F0EAE3",
  inkInverse: "#F4F6F1",
  muted: "#A89C90",
  mutedInverse: "#C8BCAE",
  subtle: "#93867B",
  line: "#3C3129",
  lineStrong: "#4D3F33",

  brand: "#F0876B",
  brandPressed: "#B84A2F",
  brandSoft: "#3A211B",
  brandSoftStrong: "#4C2C22",
  brandDeep: "#3D2A08",
  brandAccent: "#F0C97F",
  brandHighlight: "#D0A04C",
  brandAccentSoft: "rgba(240,201,127,0.14)",
  onBrand: "#FFFFFF",

  loss: "#A39B90",
  lossSolid: "#3B352E",
  lossPressed: "#2C2722",
  lossSoft: "#2A2420",
  lossAccent: "#A39B90",
  lossAccentLight: "#C9C1B6",

  danger: "#F0876B",
  dangerSolid: "#B84A2F",
  dangerPressed: "#A03D28",
  dangerSoft: "#3A211B",
  dangerAccent: "#F2B8AE",
  dangerAccentLight: "#FFD3CC",

  amber: "#D9A75B",
  amberSoft: "#322718",
  amberLine: "#4A3D22",
  amberAccent: "#FFD99B",

  heroTop: "#1D0D08",
  heroBottom: "#0E0503",
  heroLine: "rgba(240,201,127,0.22)",

  white: "#FFFFFF",
  black: "#000000",
  overlay: "rgba(0, 0, 0, 0.60)",
  inkOverlay8: "rgba(255,255,255,0.10)",
  whiteSoft: "rgba(255,255,255,0.08)",
  whiteOverlay10: "rgba(255,255,255,0.10)",
  whiteOverlay12: "rgba(255,255,255,0.12)",
  whiteOverlay15: "rgba(255,255,255,0.15)",
  whiteOverlay16: "rgba(255,255,255,0.16)",
  whiteOverlay22: "rgba(255,255,255,0.22)",
  whiteLine: "rgba(255,255,255,0.28)",
  lockCover: "rgba(255,255,255,0.96)",
  toastSuccessBg: "rgba(150,42,32,0.96)",
  toastWarningBg: "rgba(56,38,8,0.97)",
  toastErrorBg: "rgba(24,21,18,0.97)",
};

export const colorSchemeName: "light" | "dark" =
  Appearance.getColorScheme() === "dark" ? "dark" : "light";

export const colors: Readonly<Record<keyof typeof lightColors, string>> =
  colorSchemeName === "dark" ? darkColors : lightColors;

export const gradients = {
  // 仅用于已发布预测主卡：同一深红色相内的明度变化，不做彩色渐变。
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
      shadowColor: "#1A120E",
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.03,
      shadowRadius: 6,
    },
    android: { elevation: 0 },
    default: {},
  }),
  float: Platform.select({
    ios: {
      shadowColor: "#1A120E",
      shadowOffset: { width: 0, height: 12 },
      shadowOpacity: 0.16,
      shadowRadius: 28,
    },
    android: { elevation: 8 },
    default: {},
  }),
  header: Platform.select({
    ios: {
      shadowColor: "#1A120E",
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
