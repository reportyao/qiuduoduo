import type { ExpoConfig } from "expo/config";

const config: ExpoConfig = {
  name: "球多多",
  slug: "jieqiu",
  version: "0.3.2",
  orientation: "portrait",
  userInterfaceStyle: "light",
  scheme: "jieqiu",
  platforms: ["android", "ios"],
  newArchEnabled: true,
  icon: "./assets/icon.png",
  splash: {
    image: "./assets/splash-icon.png",
    resizeMode: "contain",
    backgroundColor: "#F5F4EF",
  },
  ios: {
    bundleIdentifier: "com.qiuduoduo.app",
    buildNumber: "4",
    supportsTablet: true,
    infoPlist: {
      NSAppTransportSecurity: {
        NSAllowsArbitraryLoads: false,
        NSAllowsLocalNetworking: true,
      },
    },
  },
  android: {
    package: "com.qiuduoduo.app",
    versionCode: 7,
    permissions: ["POST_NOTIFICATIONS"],
    adaptiveIcon: {
      foregroundImage: "./assets/adaptive-icon.png",
      backgroundColor: "#F5F4EF",
    },
  },
  extra: {
    // JPush AppKey 是可公开的客户端标识；Master Secret 只放服务端。
    jpushAppKey: process.env.EXPO_PUBLIC_JPUSH_APPKEY ?? "838fd4617f14e23ff4bbfcdd",
    jpushChannel: process.env.EXPO_PUBLIC_JPUSH_CHANNEL ?? "developer-default",
  },
  plugins: [
    "expo-router",
    "./plugins/withJPush",
    [
      "expo-image-picker",
      {
        photosPermission: "球多多需要访问相册，仅用于选择你的个人头像；照片只保存在本机。",
        cameraPermission: false,
        microphonePermission: false,
      },
    ],
  ],
  experiments: {
    typedRoutes: true,
  },
};

export default config;
