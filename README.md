# 江苏高职提前招生院校导航器

> 面向准备参加**江苏省高职院校提前招生**的学生的 Windows 桌面工具：
> 浏览、搜索、筛选省内高职（专科）院校，一键打开各校官方的**提前招生页面**，
> 一键在百度地图中查看学校位置与**到目标学校的驾车路线**，并给出**直线距离**参考。

本软件是**信息整理与导航工具**，不是官方招生平台，也不对学校做任何排名或评价。

---

## 一、功能一览

| 功能 | 说明 |
| --- | --- |
| 院校浏览 | 卡片式列表，展示校名、城市、办学性质（公办/民办）、地址、直线距离 |
| 搜索 | 支持校名、简称、城市、关键词（如「南京」「铁道」「民办」），多关键词按 AND 匹配 |
| 筛选 | 城市（江苏 13 个设区市）、办学性质（全部/公办/民办） |
| 排序 | 默认（城市→校名）、A-Z、**距离最近**、公办优先、民办优先 |
| 详情页 | 全部字段 + 提前招生页面年度与核验状态 + 数据来源 + 免责声明 |
| 一键打开 | 提前招生官网 →（无则）招生官网 →（无则）学校官网，用**系统默认浏览器**打开 |
| 百度地图 | 生成「常州武进洛阳高级中学 → 该校」的**驾车路线**页面；失败自动退化为地点搜索 |
| 直线距离 | Haversine 公式计算，显示为「距离…约 XX.X km（直线距离）」 |
| 收藏 / 最近浏览 | 本地保存，范围可切换为「全部学校 / 我的收藏 / 最近浏览」 |
| 复制学校信息 | 一键把校名、城市、性质、地址、官网、提前招生页复制到剪贴板 |
| 数据来源 | 列出官方政策文件与数据来源，可点击跳转 |
| 数据更新 | 可选：配置 `update_url` 后可从远程拉取新的 `schools.json`（失败自动回退，绝不覆盖） |
| 数据年度提示 | 顶部常驻显示「数据年度：2026 年」与核验日期，避免误用往年简章 |

软件**不含内置浏览器**，也不要求安装百度地图客户端——所有跳转都交给系统默认浏览器，
兼容 Edge / Chrome / Firefox 等任意浏览器。

---

## 二、运行源码

```bash
# 1. 安装依赖（Python 3.12+，本机已在 3.14 验证）
py -m pip install -r requirements.txt

# 2. 启动
py main.py
```

目录结构：

```
jsvoc-nav/
├── main.py                     # 程序入口（含 --selftest 自检模式）
├── requirements.txt
├── build_exe.bat               # 一键打包
├── data/
│   ├── schools.json            # ★ 院校数据（程序只读它，更新数据只需替换此文件）
│   ├── config.json             # 配置（参照点、数据更新地址、界面偏好）
│   ├── sources.json            # 官方来源清单（界面「数据来源」用）
│   └── excluded.json           # 未收录院校及原因（可追溯）
├── src/
│   ├── models/                 # School / OriginPoint
│   ├── data/                   # SchoolRepository（加载、校验、筛选、排序）
│   ├── services/               # distance / map / browser / config / favorites / update / storage
│   └── ui/                     # main_window / school_card / school_detail / style
├── tools/                      # 数据采集与维护脚本（见第六节）
├── tests/                      # 58 个自动化测试（含 8 项验收测试）
├── assets/                     # 图标
└── build/pyinstaller.spec      # 打包配置
```

---

## 三、数据说明（重要）

### 3.1 数据口径

江苏省教育考试院《省教育厅关于做好江苏省 2026 年高职院校提前招生改革试点工作的通知》
（苏教考函〔2026〕1号）明确：

> **省内高职（专科）院校以及教育部批准的省外高职（专科）院校均可申请参加**高职院校提前招生。

官方**不在网站上公布「参加提前招生的院校名单」**（名单只在考生服务平台 `gk.jseea.cn` 内）。
因此本软件采用的口径是：

> **收录江苏省内、且已逐校核验到 2026 年提前招生相关页面的高职（专科）院校。**

未核验到的院校**不收录**，但会连同原因保留在 `data/excluded.json` 中，方便人工复核后补入。

### 3.2 数据字段与溯源

`data/schools.json` 中每所院校都保留了：

- `early_admission_url` / `early_admission_year` / `early_admission_confidence`
  （`high` = 学校自有域名且页面确含「提前招生」；`medium` = 第三方转载页或官方页无法直连核验）
- `early_admission_third_party`：链接是否为第三方转载（此类链接**不会**冒充「官方提前招生页」按钮，只会作为参考）
- `source_url` / `last_verified`：数据来源与核验日期
- `latitude` / `longitude` / `coord_confidence`：坐标及其置信度

**软件不会编造数据**：拿不到的字段一律留空（UI 显示「暂无数据」），不猜学校、不拼 URL、不伪造坐标。

### 3.3 数据来源

| 类型 | 来源 |
| --- | --- |
| 官方政策 | 江苏省教育考试院 `www.jseea.cn`（政策文件、工作问答、第二轮通告等） |
| 官方平台 | 考生服务平台 `gk.jseea.cn`；教育部全国高等学校名单 |
| 提前招生页面 | **各院校官网/招生网**（逐校实际抓取并验证可达） |
| 基础名单/官网/地址 | 掌上高考 `api.eol.cn`、`static-data.gaokao.cn`（第三方公开数据，仅作线索） |
| 经纬度 | OpenStreetMap（Photon，**非官方数据**，低置信一律不采用） |

### 3.4 关于距离

- 界面显示的是 **直线距离**（Haversine 大圆距离），**不是驾车距离**，已在文案中明确标注；
- 真正的驾车距离请点击「百度地图」由地图服务计算；
- 缺少坐标的院校显示「暂无距离数据」，不会用 0 或猜测值糊弄。

---

## 四、修改参照地点（默认：常州武进洛阳高级中学）

编辑 `data/config.json`：

```json
{
  "origin": {
    "name": "常州武进洛阳高级中学",
    "address": "江苏省常州市武进区洛阳镇",
    "latitude": 31.6467631,
    "longitude": 120.082389,
    "source": "OpenStreetMap（Photon 查询『武进区洛阳高级中学』命中 OSM way 863559198，非官方数据）"
  }
}
```

把 `name` / `latitude` / `longitude` 换成你自己的目标学校即可（重新启动软件生效）。
若不确定坐标，可留空 `latitude`/`longitude`——此时距离功能自动降级为「暂无距离数据」，
百度地图仍可用（改用文字地址导航）。

> 坐标来源为 OpenStreetMap，**非官方数据**，可能与实际校门位置有数十~数百米偏差，仅供参考。

---

## 五、百度地图功能说明

点击任一院校的「百度地图」按钮时，软件会生成并打开如下链接（所有参数按标准 URL 编码）：

```
https://api.map.baidu.com/direction
    ?origin=latlng:31.6467631,120.082389|name:常州武进洛阳高级中学
    &destination=latlng:32.0640583,118.9149113|name:南京交通职业技术学院
    &mode=driving&region=江苏&output=html&src=webapp.jsvoc-nav
```

- `origin` 为参照点（默认洛阳高级中学），`destination` 为当前院校，`mode=driving` 为驾车；
- 有坐标时使用精确经纬度，无坐标时退化为文字名称（由 `region=江苏` 消歧）；
- 若路线链接打开失败，会自动退化为 `https://map.baidu.com/search/<校名 地址>` 地点搜索页，
  保证用户至少能看到学校位置；
- 中文、空格、括号等一律使用 `urllib.parse.quote` / `urlencode` 编码，不手工拼接 URL。

---

## 六、更新学校数据

### 6.1 只改数据、不动程序（推荐）

1. 用新的 `schools.json` 替换 exe 同级 `data/schools.json`（没有该目录就新建）；
2. 重新打开软件即可 —— 程序**优先读取 exe 同级的 `data/schools.json`**，
   读不到才回退到打包进 exe 的内置数据。

> 配置文件位置同理：exe 同级 `data/config.json`。

### 6.2 重新采集（需要联网）

```bash
py tools/collect_base.py            # 1. 采集省内高职专科院校基础名单（名称/城市/官网/招生网/地址）
py tools/verify_early_admission.py  # 2. 逐校核验 2026 提前招生页面（并发，可 --retry-failed 续跑）
py tools/merge_verification.py      # 3. 合并人工/子代理复核结果（data/_agent*/）
py tools/geocode.py                 # 4. 采集坐标（Photon，低置信自动留空）
py tools/build_dataset.py           # 5. 合成 data/schools.json 与 data/excluded.json
py tools/validate_data.py           # 6. 数据体检（有 ERROR 会返回非 0）
py tools/report.py                  # 7. 生成 tools/report.md 数据报告
```

`tools/report.md` 会列出**需人工确认清单**：第三方转载链接、指向事务性内容（成绩查询等）的链接、
缺坐标院校、坐标命中分校区/邻校的院校、未收录院校及原因。

### 6.3 远程自动更新（可选）

在 `data/config.json` 中配置：

```json
{ "update_url": "https://你的域名或 GitHub Raw 地址/schools.json" }
```

配置后，软件启动时会在**后台线程**静默检查更新；留空则**完全不联网**。安全约束：

- 网络失败 / 超时 / 404 → 继续使用本地数据；
- 远程数据为空、非 JSON、无有效院校记录 → **拒绝写入**；
- 成功写入前先把原文件备份为 `schools.json.bak`，再原子替换。

---

## 七、打包 EXE

```bash
build_exe.bat
```

或手动执行：

```bash
py -m pip install -r requirements.txt
py tools/make_icon.py
py -m PyInstaller --noconfirm --clean build/pyinstaller.spec
```

产物：**`dist/江苏高职提前招生.exe`**（单文件，约 49 MB，双击即可运行，用户无需安装 Python）。

发布建议同时提供 `data/schools.json`（与 exe 同级放置即可覆盖内置数据）。

### 自检与排障

windowed exe 没有控制台，可用自检模式查看「程序到底读了哪个数据文件」：

```bat
江苏高职提前招生.exe --selftest selftest.txt
```

会输出：`frozen`、`_MEIPASS`、候选数据文件及其存在性、实际加载的院校数与年度、`update_url` 等。

---

## 八、测试

```bash
py -m pytest tests/ -q
```

- `tests/test_acceptance.py`：需求中的 **8 项验收测试**（搜索南京、筛选民办、打开提前招生官网、
  百度地图驾车路线、直线距离显示、无提前招生页回退招生网、断网启动仍可用、坏 URL 不崩溃）
- `tests/test_models_and_repository.py`：模型容错、仓储加载/筛选/排序
- `tests/test_services.py`：Haversine 精度、URL 编码、浏览器协议白名单
- `tests/test_update_service.py`：数据更新失败路径不覆盖本地数据

---

## 九、本次交付摘要

| 项目 | 数值 |
| --- | --- |
| 收录院校 | **84 所**（公办 **62** 所、民办 **22** 所） |
| 数据年度 | 2026（核验日期 2026-09-18） |
| 提前招生页面 | 自有域名核验通过 77 所；第三方转载参考 6 所（另有 1 所为官方页但无法直连核验） |
| 可算直线距离 | 58 所（其余 26 所因 OpenStreetMap 无可靠坐标而留空） |
| 未收录 | 4 所（见 `data/excluded.json`） |
| 可执行文件 | `dist/江苏高职提前招生.exe` |

> 民办 22 所中含 1 所中外合作办学（苏州百年职业学院），在筛选上归入「民办」，
> 数据中保留 `ownership_note = 中外合作办学` 说明。

---

## 十、免责声明

> 本软件仅用于整理和导航江苏省高职院校提前招生相关公开信息，不属于江苏省教育考试院或任何高校官方招生平台。
> 招生政策、招生计划、报考条件、校测方式及录取规则等信息可能发生变化，请以江苏省教育考试院及各招生院校官方发布的信息为准。

补充说明：

- 本软件**不对学校进行任何排名、评分或推荐**，仅提供客观信息与官方入口导航；
- 院校的「是否参加提前招生」以当年江苏省教育考试院及各校官方发布为准，
  软件中的数据为整理时点的核验结果，可能滞后于最新发布；
- 经纬度来自 OpenStreetMap，非官方数据，存在偏差可能，直线距离仅供参考；
- 部分院校官网会拦截自动化访问，此类院校的提前招生链接可能指向第三方转载页，已在数据中明确标注。
