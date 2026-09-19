# 江苏高职提前招生 —— Android 版（原生 APK）

与桌面版（`../`）共用**同一份院校数据**（`../data/schools.json`），
界面用 **Kotlin + Jetpack Compose** 原生实现——不使用 WebView 壳，
因此不存在「字体缺失、按钮点不动」这类 Web 容器问题。

## 一、功能对照（与桌面版保持一致）

| 功能 | Android 版 |
| --- | --- |
| 院校浏览 | `LazyColumn` 卡片列表（校名 / 城市 · 办学性质 / 地址 / 直线距离） |
| 搜索 | 支持校名、简称、城市、关键词，多关键词按 AND 匹配 |
| 筛选 | 城市（横向 chips）、办学性质（全部/公办/民办） |
| 范围 | 全部院校 / 我的收藏 / 最近浏览 |
| 排序 | 默认（城市→校名）、A-Z、距离最近、公办优先、民办优先 |
| 详情页 | 全字段 + 数据溯源 + 核验状态 + 免责声明 |
| 一键打开 | 提前招生简章 / 提前招生栏目（自动区分）→ 招生网 → 学校官网 |
| 其他入口 | 学校官网、招生网、招生简章、招生计划、**录取结果**、**考试资料**（无链接则隐藏） |
| 百度地图 | 优先唤起**百度地图 App** 规划「参照点 → 该校」驾车路线；未安装则回落网页版 |
| 直线距离 | Haversine 计算，明确标注「直线距离」，非驾车距离 |
| 收藏 / 最近浏览 | 本地保存（SharedPreferences） |
| 复制学校信息 | 一键复制全部字段与免责声明 |
| 数据更新 | 菜单「检查数据更新」，未配置地址时**完全不联网**，失败保留本地数据 |
| 深色模式 | 跟随系统（Material3 动态配色关闭，使用与桌面版一致的主题令牌） |

## 二、构建环境

| 组件 | 要求 | 本机实测 |
| --- | --- | --- |
| JDK | 17+（Gradle 8.14 起支持 Java 24） | **JDK 24**（`C:\Program Files\Java\jdk-24`） |
| Android SDK | Platform 34/36 + Build-Tools + platform-tools | `%LOCALAPPDATA%\Android\Sdk`（已含 android-34/36、build-tools 34/35） |
| Gradle | 8.14.3（AGP 8.11 要求 Gradle 8.13+） | 项目自带 wrapper；或本地发行版 |

`local.properties` 需指向本机 SDK（已加入 `.gitignore`）：

```properties
sdk.dir=C\:\\Users\\<用户名>\\AppData\\Local\\Android\\Sdk
```

或设置环境变量 `ANDROID_HOME`。

## 三、构建 APK

```powershell
# 方式一：用项目自带 wrapper（首次会自动下载 Gradle）
cd android
.\gradlew.bat assembleDebug        # 调试包
.\gradlew.bat assembleRelease      # 发布包（未签名）

# 方式二：用本地 Gradle 发行版
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
.\tools\gradle-8.14.3\bin\gradle.bat assembleDebug
```

产物：`android/app/build/outputs/apk/debug/app-debug.apk`

> 依赖仓库已在 `settings.gradle.kts` 中配置为阿里云镜像 + 官方仓库兜底
> （国内直连 Google Maven 通常不可达）。

## 四、安装到手机

```powershell
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
& "$env:ANDROID_HOME\platform-tools\adb.exe" devices          # 确认设备已授权
& "$env:ANDROID_HOME\platform-tools\adb.exe" install -r app\build\outputs\apk\debug\app-debug.apk
```

手机需开启「开发者选项 → USB 调试」。首次安装后即可离线使用（数据已内置）。

## 五、数据从哪来

- 构建时由 Gradle task `syncDataset` 自动把 `../data/schools.json` 复制进
  `app/src/main/assets/`，保证两端数据一致；
- App 运行时优先读取私有目录 `filesDir/schools.json`（数据更新写入的位置），
  读不到才回落到内置 assets；
- 更新地址在桌面版 `data/config.json` 与 Android 的偏好设置中都可以配置，
  指向同一份托管 JSON（例如 GitHub Raw）即可两端同步。

## 六、目录结构

```
android/
├── settings.gradle.kts          # 仓库镜像配置
├── build.gradle.kts             # 插件版本（AGP 8.11.1 / Kotlin 2.1.0）
├── gradle.properties
├── local.properties             # 本机 SDK 路径（不入库）
└── app/
    ├── build.gradle.kts         # compileSdk 36 / minSdk 24 / Compose / 数据同步 task
    └── src/main/
        ├── AndroidManifest.xml
        ├── assets/schools.json  # 构建时自动同步
        ├── res/                 # 图标、主题、深浅色启动底色
        └── java/com/jsvocnav/app/
            ├── MainActivity.kt
            ├── data/            # School / SchoolRepository / LocalStore
            ├── service/         # DistanceService / LinkService / UpdateService
            └── ui/              # MainScreen / SchoolCardView / SchoolDetailScreen / InfoDialogs / theme
```

## 七、已知限制

- **直线距离**来自 OpenStreetMap 坐标（非官方数据），约 1/3 院校因无可靠坐标而显示「暂无距离数据」；
- 少数院校的提前招生入口是**第三方转载页**（数据里已标注「简章为第三方转载」）；
- 未签名的 release 包需要自行签名后才能上架或分享安装；
- 录取结果、考试资料等入口**时效性强**，过期页面请以学校官网为准。
