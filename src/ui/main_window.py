"""主窗口：侧栏筛选 + 卡片式院校列表。

界面结构（对应需求中的草图）::

    ┌──────────────────────────────────────────────┐
    │ 江苏高职提前招生          2026  [数据来源][检查更新] │
    ├──────────────┬───────────────────────────────┤
    │ 搜索学校...    │  江苏某某职业技术学院          │
    │ 城市 [全部▾]  │  南京 · 公办        [★]        │
    │ 性质 [全部▾]  │  地址 XXXXXXXX                 │
    │ 排序 [默认▾]  │  [提前招生官网][百度地图][详情] │
    │ 全部/收藏/最近 │  ...                           │
    └──────────────┴───────────────────────────────┘

数据在加载完成后立即展示，**启动时不强制联网**；只有配置了「数据更新地址」
时才在后台静默检查更新。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.data.school_repository import (
    FILTER_ALL,
    SORT_LABELS,
    RepositoryError,
    SchoolRepository,
    project_root,
)
from src.models.origin import OriginPoint
from src.models.school import OWNERSHIP_PRIVATE, OWNERSHIP_PUBLIC, School
from src.services.browser_service import BrowserService
from src.services.config_service import ConfigService
from src.services.distance_service import DistanceService
from src.services.favorites_service import FavoritesService, RecentService
from src.services.map_service import MapService
from src.services.update_service import UpdateService
from src.ui.school_card import SchoolCard
from src.ui.school_detail import (
    DISCLAIMER_TEXT,
    DataSourceDialog,
    SchoolDetailDialog,
    SimpleTextDialog,
)
from src.ui.style import (
    build_palette,
    build_stylesheet,
    system_prefers_dark,
    theme_for,
)

SEARCH_DEBOUNCE_MS = 250
SCOPE_ALL = "all"
SCOPE_FAVORITES = "favorites"
SCOPE_RECENT = "recent"


class _UpdateWorker(QThread):
    """在后台线程执行更新检查，避免界面卡顿。"""

    completed = Signal(object)

    def __init__(self, service: UpdateService) -> None:
        super().__init__()
        self.service = service

    def run(self) -> None:  # noqa: D102 - QThread 约定
        try:
            result = self.service.check()
        except Exception as exc:  # noqa: BLE001 - 后台任务不能把异常抛到主线程
            from src.services.update_service import STATUS_FAILED, UpdateResult

            result = UpdateResult(STATUS_FAILED, f"检查更新时出现异常：{exc}")
        self.completed.emit(result)


class MainWindow(QMainWindow):
    """应用主窗口。"""

    def __init__(
        self,
        repository: SchoolRepository,
        config_service: ConfigService,
        *,
        favorites: FavoritesService | None = None,
        recent: RecentService | None = None,
        browser_service: BrowserService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.config_service = config_service
        self.favorites = favorites or FavoritesService()
        self.recent = recent or RecentService()
        self.browser_service = browser_service or BrowserService()

        config = self.config_service.load()
        self.origin: OriginPoint = config.origin
        self.distance_service = DistanceService(self.origin)
        self.map_service = MapService(self.origin, browser=self.browser_service)
        self.update_service = UpdateService(self.config_service, self.repository)

        self._cards: list[QWidget] = []
        self._scope = SCOPE_ALL
        self._update_worker: _UpdateWorker | None = None
        self._load_error: str = ""

        self.setWindowTitle("江苏高职提前招生院校导航器")
        self.resize(1180, 780)
        self._theme_name = ""
        self._apply_theme()
        self._watch_system_theme()

        self._build_ui()
        self._load_data()
        self._restore_geometry()
        self._maybe_check_updates()

    # ------------------------------------------------------------------ 主题
    def _apply_theme(self) -> None:
        """按系统当前主题（浅色/深色）重新应用 QSS 与调色板。

        同时设置 app 级 QPalette：QSS 只精细控制主要控件，palette 负责兜底，
        这样在深色系统下也不会出现「未被 QSS 覆盖的控件露出系统深色底 + 深色字」。
        """
        theme = theme_for(system_prefers_dark())
        app = QApplication.instance()
        if app is not None:
            app.setPalette(build_palette(theme))
        self.setStyleSheet(build_stylesheet(theme))
        self._theme_name = theme.name

    def _watch_system_theme(self) -> None:
        """跟随系统主题切换（Qt 6.5+ 的 colorSchemeChanged）。"""
        try:
            hints = QGuiApplication.styleHints()
        except Exception:  # noqa: BLE001
            return
        signal = getattr(hints, "colorSchemeChanged", None)
        if signal is not None:
            signal.connect(self._on_color_scheme_changed)

    def _on_color_scheme_changed(self, *_: object) -> None:
        """系统主题变化时重刷样式（已存在的控件由 QSS 级联自动更新）。"""
        self._apply_theme()

    # ------------------------------------------------------------------ 构建
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._build_sidebar())
        body_layout.addWidget(self._build_list_area(), 1)
        outer.addWidget(body, 1)

        outer.addWidget(self._build_status_bar())

    # ---------------------------------------------------------------- 顶部栏
    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("HeaderBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)

        title = QLabel("江苏高职提前招生")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        self.year_badge = QLabel("数据年度：—")
        self.year_badge.setObjectName("DataYearBadge")
        layout.addWidget(self.year_badge)

        self.verified_label = QLabel("")
        self.verified_label.setObjectName("HeaderHint")
        layout.addWidget(self.verified_label)

        layout.addStretch(1)

        source_button = QPushButton("数据来源")
        source_button.setCursor(Qt.CursorShape.PointingHandCursor)
        source_button.clicked.connect(self._show_sources)
        layout.addWidget(source_button)

        disclaimer_button = QPushButton("免责声明")
        disclaimer_button.setCursor(Qt.CursorShape.PointingHandCursor)
        disclaimer_button.clicked.connect(self._show_disclaimer)
        layout.addWidget(disclaimer_button)

        self.update_button = QPushButton("检查数据更新")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(lambda: self._check_updates(manual=True))
        layout.addWidget(self.update_button)

        return header

    # ---------------------------------------------------------------- 侧栏
    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(268)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索学校名、简称、城市、关键词…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self.search_timer.timeout.connect(self._refresh_cards)

        layout.addWidget(self._section_label("城市"))
        self.city_combo = QComboBox()
        self.city_combo.addItem(FILTER_ALL)
        self.city_combo.currentTextChanged.connect(self._refresh_cards)
        layout.addWidget(self.city_combo)

        layout.addWidget(self._section_label("办学性质"))
        self.ownership_combo = QComboBox()
        for value in (FILTER_ALL, OWNERSHIP_PUBLIC, OWNERSHIP_PRIVATE):
            self.ownership_combo.addItem(value)
        self.ownership_combo.currentTextChanged.connect(self._refresh_cards)
        layout.addWidget(self.ownership_combo)

        layout.addWidget(self._section_label("排序"))
        self.sort_combo = QComboBox()
        for value, label in SORT_LABELS:
            self.sort_combo.addItem(label, value)
        self.sort_combo.currentIndexChanged.connect(self._refresh_cards)
        layout.addWidget(self.sort_combo)

        layout.addWidget(self._section_label("列表范围"))
        self.scope_group = QButtonGroup(self)
        self.scope_group.setExclusive(True)
        for value, label in (
            (SCOPE_ALL, "全部学校"),
            (SCOPE_FAVORITES, "我的收藏"),
            (SCOPE_RECENT, "最近浏览"),
        ):
            button = QPushButton(label)
            button.setObjectName("ScopeButton")
            button.setCheckable(True)
            button.setChecked(value == SCOPE_ALL)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, v=value: self._set_scope(v))
            self.scope_group.addButton(button)
            layout.addWidget(button)

        layout.addStretch(1)

        self.sidebar_stats = QLabel("")
        self.sidebar_stats.setObjectName("CardMeta")
        self.sidebar_stats.setWordWrap(True)
        layout.addWidget(self.sidebar_stats)

        note = QLabel("本软件只做信息导航，不是官方招生平台。")
        note.setObjectName("DisclaimerText")
        note.setWordWrap(True)
        layout.addWidget(note)

        return sidebar

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SidebarTitle")
        return label

    # ---------------------------------------------------------------- 列表
    def _build_list_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(18, 16, 18, 16)
        self.list_layout.setSpacing(12)
        self.list_layout.addStretch(1)
        self.scroll_area.setWidget(self.list_container)

        layout.addWidget(self.scroll_area)
        return container

    def _build_status_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(12)

        self.status_label = QLabel("正在加载数据…")
        self.status_label.setObjectName("CardMeta")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.source_label = QLabel("")
        self.source_label.setObjectName("CardMeta")
        layout.addWidget(self.source_label)
        return bar

    # ------------------------------------------------------------------ 数据
    def _load_data(self) -> None:
        try:
            loaded = self.repository.load(force=True)
        except RepositoryError as exc:
            self._load_error = str(exc)
            self._show_load_error(str(exc))
            return

        self._load_error = ""
        data_year = loaded.data_year
        self.year_badge.setText(f"数据年度：{data_year} 年" if data_year else "数据年度：未知")
        self.verified_label.setText(
            f"核验日期 {loaded.last_verified}" if loaded.last_verified else ""
        )
        self.source_label.setText(f"数据文件：{Path(loaded.source_path).name}")

        # 城市筛选：全部 + 数据中出现过的城市
        current_city = self.city_combo.currentText() or FILTER_ALL
        self.city_combo.blockSignals(True)
        self.city_combo.clear()
        self.city_combo.addItem(FILTER_ALL)
        for city in loaded.cities:
            self.city_combo.addItem(city)
        index = self.city_combo.findText(current_city)
        self.city_combo.setCurrentIndex(index if index >= 0 else 0)
        self.city_combo.blockSignals(False)

        summary = self.repository.loading_summary()
        self.sidebar_stats.setText(
            f"共 {summary['total']} 所院校\n"
            f"公办 {summary['public']} · 民办 {summary['private']}\n"
            f"可显示距离 {summary['with_coordinates']} 所"
        )

        if loaded.warnings:
            # 数据文件有脏记录：不打断使用，只在状态栏提示
            self.status_label.setToolTip("\n".join(loaded.warnings))

        self._refresh_cards()

    def _show_load_error(self, message: str) -> None:
        """数据完全不可用时的兜底界面（满足「不因数据问题崩溃」）。"""
        self._clear_cards()
        error_card = QFrame()
        error_card.setObjectName("SchoolCard")
        layout = QVBoxLayout(error_card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title = QLabel("未能加载院校数据")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        body = QLabel(
            f"{message}\n\n"
            "请确认 data/schools.json 存在且为合法 JSON。\n"
            "可以把官方提供的数据文件放回该位置后重新打开软件。"
        )
        body.setWordWrap(True)
        body.setObjectName("CardAddress")
        layout.addWidget(body)

        reload_button = QPushButton("重新加载数据")
        reload_button.clicked.connect(self._load_data)
        layout.addWidget(reload_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.list_layout.insertWidget(0, error_card)
        self._cards.append(error_card)
        self.status_label.setText("数据加载失败")

    # ------------------------------------------------------------------ 渲染
    def _clear_cards(self) -> None:
        for card in self._cards:
            self.list_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def _all_schools(self) -> list[School]:
        try:
            return list(self.repository.load().schools)
        except RepositoryError:
            return []

    def _scoped_schools(self) -> list[School]:
        schools = self._all_schools()
        if self._scope == SCOPE_FAVORITES:
            ids = set(self.favorites.ids)
            return [s for s in schools if s.id in ids]
        if self._scope == SCOPE_RECENT:
            order = self.recent.ids
            by_id = {s.id: s for s in schools}
            return [by_id[i] for i in order if i in by_id]
        return schools

    def _refresh_cards(self) -> None:
        if self._load_error:
            return

        keyword = self.search_edit.text().strip()
        city = self.city_combo.currentText() or FILTER_ALL
        ownership = self.ownership_combo.currentText() or FILTER_ALL
        sort = self.sort_combo.currentData() or "default"

        candidates = self._scoped_schools()
        distances = self.distance_service.distance_map(candidates)
        visible = self.repository.query(
            candidates,
            keyword=keyword,
            city=city,
            ownership=ownership,
            sort=sort,
            distances=distances,
        )

        favorite_ids = set(self.favorites.ids)
        distance_texts = self.distance_service.format_map(visible)

        self._clear_cards()
        for school in visible:
            card = SchoolCard(
                school,
                distance_text=distance_texts.get(school.id, ""),
                is_favorite=school.id in favorite_ids,
            )
            card.openExternalRequested.connect(self._open_external)
            card.openMapRequested.connect(self._open_map)
            card.detailRequested.connect(self._show_detail)
            card.favoriteToggled.connect(self._toggle_favorite_clicked)
            self.list_layout.insertWidget(len(self._cards), card)
            self._cards.append(card)

        total = len(candidates)
        self.status_label.setText(
            f"共 {len(self._all_schools())} 所院校"
            + (f"　当前范围 {total} 所" if self._scope != SCOPE_ALL else "")
            + f"　显示 {len(visible)} 所"
        )

        if not visible:
            empty = QLabel(self._empty_hint())
            empty.setObjectName("CardMeta")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(160)
            empty.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            self.list_layout.insertWidget(0, empty)
            self._cards.append(empty)

    def _empty_hint(self) -> str:
        if self._scope == SCOPE_FAVORITES:
            return "还没有收藏任何院校。点击卡片右上角的 ☆ 即可收藏。"
        if self._scope == SCOPE_RECENT:
            return "还没有浏览记录。打开任意院校的「查看详情」后会记录在这里。"
        return "没有符合条件的院校，试试更换筛选条件或关键词。"

    # ------------------------------------------------------------------ 交互
    def _on_search_changed(self) -> None:
        self.search_timer.start()  # 防抖：停止输入 250ms 后才刷新

    def _set_scope(self, scope: str) -> None:
        self._scope = scope
        self._refresh_cards()

    def _toggle_favorite_clicked(self, school: School) -> None:
        favorite = self.favorites.toggle(school.id)
        for card in self._cards:
            if isinstance(card, SchoolCard) and card.school.id == school.id:
                card.set_favorite(favorite)
        if self._scope == SCOPE_FAVORITES:
            self._refresh_cards()

    def _open_admission(self, school: School) -> None:
        url, _ = school.admission_entry
        self._open_external(school, url)

    def _open_external(self, school: School, url: str) -> None:
        """打开卡片/详情页上的某个收录链接（统一处理失败与复制）。"""
        if not url:
            QMessageBox.information(self, "暂无链接", "该校未收录到可打开的链接。")
            return
        outcome = self.browser_service.open(url)
        if not outcome.ok:
            self._show_open_failure("无法打开链接", outcome.message, url)

    def _open_map(self, school: School) -> None:
        outcome = self.map_service.open_directions(school)
        if not outcome.ok:
            self._show_open_failure("无法打开百度地图", outcome.message, outcome.url)

    def _show_open_failure(self, title: str, message: str, url: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(message or "打开链接失败")
        if url:
            box.setInformativeText(url)
            copy_button = box.addButton("复制网址", QMessageBox.ButtonRole.ActionRole)
        else:
            copy_button = None
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if copy_button is not None and box.clickedButton() is copy_button:
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(url)

    def _show_detail(self, school: School) -> None:
        self.recent.record(school.id)
        dialog = SchoolDetailDialog(
            school,
            distance_service=self.distance_service,
            map_service=self.map_service,
            browser_service=self.browser_service,
            is_favorite=self.favorites.is_favorite(school.id),
            parent=self,
        )
        dialog.favoriteChanged.connect(self._toggle_favorite_clicked)
        dialog.exec()
        if self._scope == SCOPE_RECENT:
            self._refresh_cards()

    def _show_disclaimer(self) -> None:
        SimpleTextDialog(
            "免责声明",
            DISCLAIMER_TEXT
            + "\n\n"
            "关于距离：界面显示的是「直线距离」（大圆距离），"
            "不是驾车距离，实际出行请以地图导航结果为准。\n\n"
            "关于数据：院校名单与提前招生页面来自公开信息整理，"
            "已尽力逐校核验，但可能滞后于院校官网的最新发布。",
            self,
        ).exec()

    def _show_sources(self) -> None:
        sources = self._load_sources()
        DataSourceDialog(sources, browser_service=self.browser_service, parent=self).exec()

    @staticmethod
    def _load_sources() -> Mapping[str, Any]:
        path = project_root() / "data" / "sources.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"data_year": "未知", "generated_at": "未知"}

    # ------------------------------------------------------------------ 更新
    def _maybe_check_updates(self) -> None:
        """启动时静默检查：仅当配置了 update_url 时才联网（不阻塞界面）。"""
        if not (self.config_service.load().update_url or "").strip():
            return
        self._check_updates(manual=False)

    def _check_updates(self, *, manual: bool) -> None:
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        self.update_button.setEnabled(False)
        self.update_button.setText("检查中…")
        worker = _UpdateWorker(self.update_service)
        worker.completed.connect(
            lambda result: self._on_update_finished(result, manual=manual)
        )
        worker.finished.connect(worker.deleteLater)
        self._update_worker = worker
        worker.start()

    def _on_update_finished(self, result: Any, *, manual: bool) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText("检查数据更新")
        self._update_worker = None

        if result.status == "updated":
            self._load_data()
            if manual:
                QMessageBox.information(self, "数据已更新", result.message)
            return
        if manual:
            icon = (
                QMessageBox.Icon.Information
                if result.status in ("up_to_date", "skipped")
                else QMessageBox.Icon.Warning
            )
            QMessageBox(icon, "检查更新", result.message, parent=self).exec()

    # -------------------------------------------------------------- 窗口状态
    def _restore_geometry(self) -> None:
        geometry = self.config_service.load().window_geometry
        if geometry:
            try:
                self.restoreGeometry(bytes.fromhex(geometry))
            except ValueError:
                pass

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt 约定
        config = self.config_service.load()
        config.window_geometry = bytes(self.saveGeometry()).hex()
        self.config_service.save(config)
        super().closeEvent(event)
