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

## 必需组件

JPush 6.x 要求 App 自己声明一个 `JCommonService` 子类，否则 JCore 会反复报
`AndroidManifest.xml missing required service:cn.jpush.android.service.JCommonService`
并导致推送进程不可用。当前已补：

- `native/jpush/java/JPushCommonService.java`
- `withJPush.js` 注入 `<service android:name="...JPushCommonService"
  android:process=":pushcore" android:exported="true">`，action 为
  `cn.jiguang.user.service.action`

## 实测记录（2026-11-06）

构建：APK 18（`0.3.0`，versionCode 5，JPush 6.3.0/JCore 5.6.0，新架构）。
设备：MuMu 模拟器 Android 12（x86_64，Houdini arm64 转译）。

- `JPushInterface.init` 成功，`JPushModule` 拿到
  `registration_id=1a0018970bf32ecca80`，`connected=true`。
- 随后 RN 启动阶段崩溃：`SIGSEGV`，new arch 在 `mqt_v_js`/`libhermes`，
  old arch（APK 19）在 `mqt_js`；崩溃点都在 JS bundle 初始化阶段。
- 隔离实验：去掉 Application 内 init、去掉 `InitProvider`、延迟初始化、
  禁用自定义 receiver、切旧架构，均不能避免；只有移除 `libjutils.so`
  或让 APK 原生库数量降下来才能启动。说明是 **MuMu/Houdini 的 arm64
  转译与 JCore 原生库不兼容**，不是 JS/业务代码问题。
- 后端 `/push` 相关 6 项测试通过：`python -m pytest -q -k push`。

**结论：需要一台真机（arm64 Android）复测。** 模拟器上只能验证到
registration id 与连接状态，不能作为“App 可正常使用”的验收。

## 真机测试包

- `apk-20261106-22`：版本 `0.3.3`（versionCode 8），在 APK 18 基础上：
  - 保留 `JCommonService`
  - 移除 JPush AAR 带入的定位、电话、外部存储、`QUERY_ALL_PACKAGES` 权限
  - `JPushReceiver` 增加 `onNotifyMessageArrived` / `onNotifyMessageOpened` 日志，
    便于验证通知到达与点击回调
  - 已复核 APK manifest：无 `READ/WRITE_EXTERNAL_STORAGE`、无定位、无电话权限
- 安装：`adb install -r qiuduoduo-apk-20261106-22.apk`
- SHA256：`70dd6216d089389477526ad403171d8f466670d051c0e0c4635f66334478dfc5`

### 真机验收清单

1. **启动不崩**：冷启动进首页，连续杀进程再启动 3 次。
2. **注册成功**：`adb logcat -s JPushModule JPush` 看到
   `registration_id=...` 与 `connected=true`。
3. **服务端绑定**：登录后进“我的 → 通知设置”，设备推送行显示已绑定；
   或 `GET /push/health` 返回 `enabled_tokens >= 1`。
4. **通知到达**：配置 Master Secret 与 `JQ_JPUSH_DRYRUN=0` 后，从 JPush
   控制台发送通知；前台/后台各测一次，确认通知栏展示。
5. **点击回调**：点通知打开 App，logcat 应出现
   `notification_opened ... extras={"deeplink":...}`。
6. **权限**：Android 13+ 首次打开推送开关时弹通知权限；拒绝后 App 不崩。

## 已知缺口（按优先级）

1. **通知点击深链未路由**：当前只记录 `notification_opened` 日志，尚未把
   `deeplink` 交给 Expo Router。真机确认点击回调后再接，避免未验证代码。
2. **退出登录未解绑 token**：`/push/unregister` 后端已有，客户端未调用；
   同一设备换账号可能收到 409。建议在登出前用旧 access token 解绑。
3. **前台通知**：未做应用内横幅/弹层；JPush 默认行为是通知栏展示。
4. **token 刷新**：只在登录后轮询 60 秒；若 registration id 晚到或更换，
   不会再次上报。建议加 AppState 回前台重试。
5. **通知权限请求时机**：只在用户打开“推送”开关时请求；未打开设置的用户
   不会收到系统权限弹窗。
6. **iOS**：未接入。

## 厂商通道

**暂未配置，以后可以补，且不影响现在这版核心接入**。厂商通道主要是提升国产
ROM 在后台/离线时的到达率；核心长连接与 registration id 已经工作。补的时候：

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

## 真机复测步骤（待执行）

1. 在 arm64 真机安装 APK 18（或后续新架构构建）。
2. `adb logcat -s JPushModule JPush` 应看到 `registration_id=...` 与
   `connected=true`，App 不应闪退。
3. 登录后进入“我的 → 通知设置”：授予通知权限；“设备推送”行应显示
   已绑定设备数（`GET /push/health` 的 `enabled_tokens`）。
4. 服务端配置 `JQ_JPUSH_MASTER_SECRET` 与 `JQ_JPUSH_DRYRUN=0` 后，用
   JPush 控制台或后端发送测试通知；先验证通知展示，再验证点击打开 App
   与 `deeplink` extras。
5. 若真机也闪退，按 `adb logcat` 的 tombstone 抓 `libhermes`/`libjutils`
   现场，再决定是否换 JPush 版本或改用厂商通道方案。

## 已知边界

- iOS 未接入；`JPushModule` 在 iOS 上为 no-op。
- 未配置厂商通道，离线/后台送达率取决于 JPush 长连接与系统保活。
- 设备 token 绑定到账号；切换账号时如果旧账号未解绑，`/push/register`
  可能返回 409，需要先 `/push/unregister` 或由后台释放。
