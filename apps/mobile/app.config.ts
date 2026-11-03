import type { ExpoConfig } from "expo/config";

const apiBaseUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://10.0.2.2:8100";

const config: ExpoConfig = {
  name: "解球",
  slug: "jieqiu",
  version: "0.1.0",
  orientation: "portrait",
  userInterfaceStyle: "automatic",
  scheme: "jieqiu",
  platforms: ["android", "ios"],
  newArchEnabled: true,
  ios: {
    bundleIdentifier: "com.jieqiu.app",
    supportsTablet: true,
    infoPlist: {
      NSAppTransportSecurity: {
        NSAllowsArbitraryLoads: false,
      },
    },
  },
  android: {
    package: "com.jieqiu.app",
    permissions: ["POST_NOTIFICATIONS"],
    adaptiveIcon: {
      backgroundColor: "#F5F4EF",
    },
  },
  plugins: ["expo-router"],
  experiments: {
    typedRoutes: true,
  },
  extra: {
    apiBaseUrl,
    appEnv: process.env.APP_ENV ?? "development",
  },
};

export default config;
