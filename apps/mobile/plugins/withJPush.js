const fs = require("fs");
const path = require("path");
const {
  withAndroidManifest,
  withAppBuildGradle,
  withDangerousMod,
  withMainApplication,
} = require("@expo/config-plugins");

const PACKAGE = "com.qiuduoduo.app";
const DEFAULT_APP_KEY = "838fd4617f14e23ff4bbfcdd";
const DEFAULT_CHANNEL = "developer-default";

/**
 * JPush 6.3.0 Android integration for Expo prebuild.
 *
 * Only JPush/JCore core AARs are bundled now. Vendor channel AARs (Xiaomi,
 * Huawei, Honor, OPPO, vivo, Meizu, FCM) are intentionally left out until the
 * operator adds their credentials; the core JPush connection still works.
 */
function withJPush(config) {
  const appKey =
    (config.extra && config.extra.jpushAppKey) ||
    process.env.EXPO_PUBLIC_JPUSH_APPKEY ||
    DEFAULT_APP_KEY;
  const channel =
    (config.extra && config.extra.jpushChannel) ||
    process.env.EXPO_PUBLIC_JPUSH_CHANNEL ||
    DEFAULT_CHANNEL;

  config = withDangerousMod(config, [
    "android",
    async (config) => {
      const projectRoot = config.modRequest.projectRoot;
      const platformRoot = config.modRequest.platformProjectRoot;
      const sourceDir = path.join(projectRoot, "native", "jpush");
      const libsDir = path.join(platformRoot, "app", "libs");
      const javaDir = path.join(
        platformRoot,
        "app",
        "src",
        "main",
        "java",
        "com",
        "qiuduoduo",
        "app",
        "jpush",
      );

      fs.mkdirSync(libsDir, { recursive: true });
      fs.mkdirSync(javaDir, { recursive: true });

      for (const file of fs.readdirSync(sourceDir)) {
        if (file.endsWith(".aar")) {
          fs.copyFileSync(path.join(sourceDir, file), path.join(libsDir, file));
        }
      }
      const javaSource = path.join(sourceDir, "java");
      for (const file of fs.readdirSync(javaSource)) {
        if (file.endsWith(".java")) {
          fs.copyFileSync(path.join(javaSource, file), path.join(javaDir, file));
        }
      }
      return config;
    },
  ]);

  config = withAppBuildGradle(config, (config) => {
    let contents = config.modResults.contents;

    if (!contents.includes("JPUSH_APPKEY")) {
      const applicationId =
        (contents.match(/applicationId\s+['"]([^'"]+)['"]/) || [])[1] || PACKAGE;
      contents = contents.replace(
        /(applicationId\s+['"][^'"]+['"]\s*\n)/,
        `$1        manifestPlaceholders = [JPUSH_PKGNAME: "${applicationId}", JPUSH_APPKEY: "${appKey}", JPUSH_CHANNEL: "${channel}"]\n`,
      );
    }

    if (!contents.includes("fileTree(dir: 'libs'")) {
      contents = contents.replace(
        /dependencies\s*\{\n/,
        "dependencies {\n    implementation fileTree(dir: 'libs', include: ['*.jar', '*.aar'])\n",
      );
    }

    config.modResults.contents = contents;
    return config;
  });

  config = withMainApplication(config, (config) => {
    let contents = config.modResults.contents;

    if (!contents.includes("JPushPackage")) {
      contents = contents.replace(
        "import com.facebook.react.ReactPackage",
        "import com.facebook.react.ReactPackage\nimport com.qiuduoduo.app.jpush.JPushPackage",
      );
      contents = contents.replace(
        "val packages = PackageList(this).packages",
        "val packages = PackageList(this).packages\n            packages.add(JPushPackage())",
      );
    }

    if (!contents.includes("JPushInterface.init")) {
      contents = contents.replace(
        "import com.facebook.react.ReactApplication",
        "import cn.jpush.android.api.JPushInterface\nimport com.facebook.react.ReactApplication",
      );
      contents = contents.replace(
        /override fun onCreate\(\) \{\n\s*super\.onCreate\(\)/,
        "override fun onCreate() {\n    super.onCreate()\n    JPushInterface.setDebugMode(BuildConfig.DEBUG)\n    JPushInterface.init(this)",
      );
    }

    config.modResults.contents = contents;
    return config;
  });

  config = withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    manifest.$ = manifest.$ || {};
    manifest.$["xmlns:tools"] = "http://schemas.android.com/tools";
    const application = manifest.application && manifest.application[0];
    if (!application) return config;

    const receiverName = `${PACKAGE}.jpush.JPushReceiver`;
    application.receiver = application.receiver || [];
    if (!application.receiver.some((item) => item.$ && item.$["android:name"] === receiverName)) {
      application.receiver.push({
        $: {
          "android:name": receiverName,
          "android:enabled": "true",
          "android:exported": "true",
        },
        "intent-filter": [
          {
            action: [{ $: { "android:name": "cn.jpush.android.intent.SERVICE_MESSAGE" } }],
            category: [{ $: { "android:name": "${applicationId}" } }],
          },
        ],
      });
    }

    // JPush's AAR declares broad permissions for optional vendor channels.
    // Keep core push working without shipping location/contacts/storage access.
    const removePermissions = [
      "android.permission.ACCESS_COARSE_LOCATION",
      "android.permission.ACCESS_FINE_LOCATION",
      "android.permission.ACCESS_BACKGROUND_LOCATION",
      "android.permission.READ_PHONE_STATE",
      "android.permission.QUERY_ALL_PACKAGES",
    ];
    manifest["uses-permission"] = manifest["uses-permission"] || [];
    for (const name of removePermissions) {
      if (!manifest["uses-permission"].some((item) => item.$ && item.$["android:name"] === name)) {
        manifest["uses-permission"].push({
          $: { "android:name": name, "tools:node": "remove" },
        });
      }
    }

    return config;
  });

  return config;
}

module.exports = withJPush;
