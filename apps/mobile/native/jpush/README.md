# JPush Android SDK

Bundled core SDK from `jpush-android-6.3.0-release.zip`:

- `jpush-android-6.3.0.aar`
- `jcore-android-5.6.0.aar`
- `push-internal-5.0.5.aar`

The app package is `com.qiuduoduo.app`; the SDK demo in the zip is already
configured with that package and AppKey `838fd4617f14e23ff4bbfcdd`.

`plugins/withJPush.js` copies these AARs and the Java bridge into the
prebuild-generated Android project, adds the manifest receiver/placeholders,
and removes JPush's optional location / phone-state / package-query
permissions.

Vendor-channel AARs (Xiaomi, Huawei, Honor, OPPO, vivo, Meizu, FCM) are **not**
bundled yet. When vendor credentials are available, add the matching AARs and
the vendor placeholders/plugin dependencies in `withJPush.js`. The core JPush
connection works without them; Chinese ROM background delivery will be less
reliable until vendor channels are configured.
