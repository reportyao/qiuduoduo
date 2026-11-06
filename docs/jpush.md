# JPush Android 接入（2026-11-06）

## 已接入

- SDK：JPush Android `6.3.0` + JCore `5.6.0` + `push-internal 5.0.5`
- 包名：`com.qiuduoduo.app`
- AppKey：`838fd4617f14e23ff4bbfcdd`（可从 `EXPO_PUBLIC_JPUSH_APPKEY` 覆盖）
- 预构建插件：`apps/mobile/plugins/withJPush.js`
- 原生桥：`apps/mobile/native/jpush/java/`
  - `JPushModule`：初始化、读取 registration id、连接状态
  - `JPushPackage`：注册 React Native 模块
  - `JPushReceiver`：接收 `onRegister` / `onConnected` 回调
- Root `usePushRegistration`：启动后轮询 registration id，调用 `POST /push/register`
- 通知设置：打开“推送”时请求 Android 13+ `POST_NOTIFICATIONS`；新增“设备推送”状态行

## 厂商通道

**暂未配置**，以后可以补：

1. 把对应厂商 AAR（`jpush-android-plugin-*.aar` 及厂商 push SDK）放到
   `apps/mobile/native/jpush/`。
2. 在 `plugins/withJPush.js` 的 `manifestPlaceholders` 中补：
   - 小米：`XIAOMI_APPID` / `XIAOMI_APPKEY`
   - 华为：`HUAWEI_APPID`（及 `agconnect-services.json`/Gradle 插件）
   - 荣耀：`HONOR_APPID`
   - OPPO：`OPPO_APPKEY` / `OPPO_APPID` / `OPPO_APPSECRET`
   - vivo：`VIVO_APPKEY` / `VIVO_APPID`
   - 魅族：`MEIZU_APPKEY` / `MEIZU_APPID`
   - FCM：`google-services.json` 与 Google Services Gradle 插件
3. 重新构建 APK。未配置厂商通道时，JPush 核心长连接仍可工作，但国产 ROM
   后台/离线送达率会低于厂商通道。

## 服务端

服务端仍需要 Master Secret 才能真正发推送：

```bash
JQ_JPUSH_APPKEY=838fd4617f14e23ff4bbfcdd
JQ_JPUSH_MASTER_SECRET=...
JQ_JPUSH_DRYRUN=0
```

未配置时 `JPushProvider` 保持 dry-run；`GET /push/health` 会显示
`dryrun=true`，通知设置页“设备推送”显示“服务端推送待配置”。

## 测试

1. 安装新版 APK，打开 App。
2. `adb logcat -s JPushModule JPush` 看 `registration_id=...`。
3. 通知设置 → 推送：授予系统通知权限；“设备推送”应显示已绑定设备数。
4. 服务端配置 Master Secret 后，用 JPush 控制台或 `/push` 发送测试通知；
   `deeplink` extras 保留在 payload 中，当前版本先验证通知展示与点击打开 App。

## 已知边界

- iOS 未接入；`JPushModule` 在 iOS 上为 no-op。
- 未配置厂商通道，离线/后台送达率取决于 JPush 长连接与系统保活。
- 设备 token 绑定到账号；切换账号时如果旧账号未解绑，`/push/register`
  可能返回 409，需要先 `/push/unregister` 或由后台释放。
