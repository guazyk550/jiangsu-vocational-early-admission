"""院校详情对话框、免责声明、数据来源。

详情页把「客观信息」与「官方入口」分开呈现：
- 上：学校名称、简称、城市、办学性质、类型、地址、官网/招生网/提前招生页；
- 中：两个大按钮（打开提前招生官网、在百度地图中查看）；
- 下：直线距离（明确标注“直线距离”，不冒充驾车距离）、数据年份、核验日期、
  数据来源，以及免责声明。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.school import CONFIDENCE_HIGH, School
from src.services.browser_service import BrowserService
from src.services.distance_service import DistanceService
from src.services.map_service import MapService

DISCLAIMER_TEXT = (
    "本软件仅用于整理和导航江苏省高职院校提前招生相关公开信息，"
    "不属于江苏省教育考试院或任何高校官方招生平台。"
    "招生政策、招生计划、报考条件、校测方式及录取规则等信息可能发生变化，"
    "请以江苏省教育考试院及各招生院校官方发布的信息为准。"
)

CONFIDENCE_HINT = {
    "high": "已在官方站点核验页面含“提前招生”",
    "medium": "链接为第三方转载页，或官方站点无法直连核验",
    "low": "页面可访问但未能确认内容",
    "none": "未找到明确的提前招生页面，将打开招生官网",
}


def _copy_to_clipboard(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


def _field_row(label: str, value: str) -> tuple[QLabel, QLabel]:
    label_widget = QLabel(label)
    label_widget.setObjectName("FieldLabel")
    value_widget = QLabel(value or "暂无数据")
    value_widget.setObjectName("FieldValue")
    value_widget.setWordWrap(True)
    value_widget.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )
    return label_widget, value_widget


class SchoolDetailDialog(QDialog):
    """某所院校的详细信息窗口。"""

    favoriteChanged = Signal(object)

    def __init__(
        self,
        school: School,
        *,
        distance_service: DistanceService,
        map_service: MapService,
        browser_service: BrowserService,
        is_favorite: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.school = school
        self.distance_service = distance_service
        self.map_service = map_service
        self.browser_service = browser_service
        self._is_favorite = is_favorite

        self.setWindowTitle(f"{school.name} — 院校详情")
        self.resize(720, 660)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # ---------------- 标题区 ----------------
        title = QLabel(school.name)
        title.setObjectName("DetailTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        meta_text = " · ".join(
            filter(None, [school.city, school.ownership, school.school_type])
        )
        meta = QLabel(meta_text)
        meta.setObjectName("CardMeta")
        layout.addWidget(meta)

        if school.ownership_note:
            note = QLabel(f"办学性质说明：{school.ownership_note}")
            note.setObjectName("CardMeta")
            note.setWordWrap(True)
            layout.addWidget(note)

        layout.addWidget(self._separator())

        # ---------------- 字段区 ----------------
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(9)
        grid.setColumnStretch(1, 1)

        rows: list[tuple[str, str]] = [
            ("学校简称", school.short_name),
            ("所在城市", f"{school.city}{(' ' + school.district) if school.district else ''}"),
            ("办学性质", school.ownership + (f"（{school.ownership_note}）" if school.ownership_note else "")),
            ("学校类型", school.school_type),
            ("学校地址", school.address),
            ("官方网站", school.official_website),
            ("招生网站", school.admission_website),
            (
                "提前招生页面",
                school.early_admission_url
                or "未找到明确的提前招生页面（将从招生网进入）",
            ),
            ("招生简章/章程", school.admission_brochure_url or "未找到"),
            ("招生计划", school.admission_plan_url or "未找到"),
        ]
        if school.early_admission_title:
            rows.append(("页面标题", school.early_admission_title))
        if school.early_admission_year:
            rows.append(("页面年度", f"{school.early_admission_year} 年"))
        rows.extend(
            [
                (
                    "页面核验",
                    CONFIDENCE_HINT.get(school.early_admission_confidence, "")
                    or school.early_admission_confidence,
                ),
                ("距参照点", self.distance_service.describe(school)),
                ("数据年份", f"{school.data_year} 年" if school.data_year else "暂无数据"),
                ("数据核验日期", school.last_verified or "暂无数据"),
            ]
        )

        for index, (label, value) in enumerate(rows):
            label_widget, value_widget = _field_row(label, value)
            grid.addWidget(label_widget, index, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value_widget, index, 1)

        layout.addLayout(grid)

        # 坐标信息（有则显示，并标注来源与置信度）
        if school.has_coordinates:
            coord_text = (
                f"{school.latitude:.6f}, {school.longitude:.6f}"
                f"（置信度 {school.coord_confidence}，来源 OpenStreetMap，非官方数据）"
            )
        else:
            coord_text = "暂无坐标数据，无法计算直线距离"
        coord_label, coord_value = _field_row("经纬度", coord_text)
        layout.addWidget(coord_label)
        layout.addWidget(coord_value)

        layout.addWidget(self._separator())

        # ---------------- 主操作按钮 ----------------
        primary_row = QHBoxLayout()
        primary_row.setSpacing(12)

        entry_url, entry_label = school.admission_entry
        admission_button = QPushButton(entry_label)
        admission_button.setObjectName("PrimaryButton")
        admission_button.setMinimumHeight(40)
        admission_button.setEnabled(bool(entry_url))
        admission_button.setCursor(Qt.CursorShape.PointingHandCursor)
        admission_button.clicked.connect(self._open_admission)
        primary_row.addWidget(admission_button, 1)

        map_button = QPushButton("在百度地图中查看")
        map_button.setMinimumHeight(40)
        map_button.setCursor(Qt.CursorShape.PointingHandCursor)
        map_button.clicked.connect(self._open_map)
        primary_row.addWidget(map_button, 1)

        layout.addLayout(primary_row)

        # ---------------- 次操作按钮 ----------------
        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(8)

        # 逐级提供常用官方入口（没有的链接直接不显示，不做死按钮）
        for label, url in (
            ("学校官网", school.official_website),
            ("招生网", school.admission_website),
            ("招生简章", school.admission_brochure_url),
            ("招生计划", school.admission_plan_url),
        ):
            if not url:
                continue
            button = QPushButton(label)
            button.setObjectName("SecondaryButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(url)
            button.clicked.connect(lambda _checked=False, target=url: self._open(target))
            secondary_row.addWidget(button)

        for label, enabled, handler in (
            ("复制学校信息", True, self._copy_info),
            ("复制网址", True, self._copy_url),
        ):
            button = QPushButton(label)
            button.setEnabled(enabled)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(handler)
            secondary_row.addWidget(button)

        self.favorite_button = QPushButton()
        self.favorite_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_button.setCheckable(True)
        self.favorite_button.setChecked(is_favorite)
        self._refresh_favorite_text()
        self.favorite_button.clicked.connect(self._toggle_favorite)
        secondary_row.addWidget(self.favorite_button)

        secondary_row.addStretch(1)
        layout.addLayout(secondary_row)

        # ---------------- 数据来源 + 免责声明 ----------------
        layout.addWidget(self._separator())

        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        source_label = QLabel("数据来源：")
        source_label.setObjectName("FieldLabel")
        source_row.addWidget(source_label)

        if school.source_url:
            source_button = QPushButton(school.source_url)
            source_button.setObjectName("LinkButton")
            source_button.setCursor(Qt.CursorShape.PointingHandCursor)
            source_button.setToolTip("打开该校提前招生页面/数据来源页面")
            source_button.clicked.connect(lambda: self._open(school.source_url))
            source_row.addWidget(source_button, 1)
        else:
            source_row.addWidget(QLabel("暂无数据"))
            source_row.addStretch(1)
        layout.addLayout(source_row)

        disclaimer = QLabel(DISCLAIMER_TEXT)
        disclaimer.setObjectName("DisclaimerText")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        layout.addStretch(1)

        # ---------------- 关闭按钮 ----------------
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("关闭")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

    # ------------------------------------------------------------------ 辅助
    @staticmethod
    def _separator() -> QFrame:
        """分隔线：颜色交给主题 QSS，避免深色模式下露出硬编码的浅色。"""
        line = QFrame()
        line.setObjectName("Separator")
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedHeight(1)
        return line

    def _refresh_favorite_text(self) -> None:
        self.favorite_button.setText("★ 已收藏" if self._is_favorite else "☆ 收藏")

    def _toggle_favorite(self) -> None:
        self._is_favorite = self.favorite_button.isChecked()
        self._refresh_favorite_text()
        self.favoriteChanged.emit(self.school)

    def _open_admission(self) -> None:
        url, _ = self.school.admission_entry
        self._open(url)

    def _open(self, url: str) -> None:
        """打开链接；失败时提示并允许复制网址。"""
        if not url:
            QMessageBox.information(self, "暂无链接", "该校没有可打开的链接。")
            return
        outcome = self.browser_service.open(url)
        if outcome.ok:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("无法打开链接")
        box.setText(outcome.message or "打开链接失败")
        box.setInformativeText(url)
        copy_button = box.addButton("复制网址", QMessageBox.ButtonRole.ActionRole)
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is copy_button:
            _copy_to_clipboard(url)

    def _open_map(self) -> None:
        outcome = self.map_service.open_directions(self.school)
        if outcome.ok:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("无法打开百度地图")
        box.setText(outcome.message or "打开地图失败")
        box.setInformativeText(outcome.url)
        copy_button = box.addButton("复制网址", QMessageBox.ButtonRole.ActionRole)
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is copy_button:
            _copy_to_clipboard(outcome.url)

    def _copy_info(self) -> None:
        """复制学校信息（用户要求的一键复制）。"""
        school = self.school
        lines = [
            f"学校名称：{school.name}",
            f"学校简称：{school.short_name}",
            f"所在城市：{school.city}",
            f"办学性质：{school.ownership}"
            + (f"（{school.ownership_note}）" if school.ownership_note else ""),
            f"学校类型：{school.school_type}",
            f"学校地址：{school.address or '暂无数据'}",
            f"官方网站：{school.official_website or '暂无数据'}",
            f"招生网站：{school.admission_website or '暂无数据'}",
            f"提前招生页面：{school.early_admission_url or '暂无数据'}",
            f"招生简章/章程：{school.admission_brochure_url or '暂无数据'}",
            f"招生计划：{school.admission_plan_url or '暂无数据'}",
            f"数据年份：{school.data_year or '暂无数据'}",
            "",
            DISCLAIMER_TEXT,
        ]
        _copy_to_clipboard("\n".join(lines))
        QMessageBox.information(self, "已复制", "学校信息已复制到剪贴板。")

    def _copy_url(self) -> None:
        url, _ = self.school.admission_entry
        if not url:
            QMessageBox.information(self, "暂无链接", "该校没有可复制的链接。")
            return
        _copy_to_clipboard(url)
        QMessageBox.information(self, "已复制", f"已复制：\n{url}")


class SimpleTextDialog(QDialog):
    """用于展示免责声明 / 使用说明等长文本。"""

    def __init__(
        self, title: str, body: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(680, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("DetailTitle")
        layout.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        text = QLabel(body)
        text.setWordWrap(True)
        text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_layout.addWidget(text)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)


class DataSourceDialog(QDialog):
    """数据来源列表（可点击打开官方页面）。"""

    def __init__(
        self,
        sources: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        *,
        browser_service: BrowserService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("数据来源")
        self.resize(700, 560)
        self.browser_service = browser_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        heading = QLabel("数据来源")
        heading.setObjectName("DetailTitle")
        layout.addWidget(heading)

        meta_label = QLabel(
            f"数据年度：{sources.get('data_year', '未知')}　"
            f"整理日期：{sources.get('generated_at', '未知')}"
            if isinstance(sources, Mapping)
            else ""
        )
        meta_label.setObjectName("CardMeta")
        layout.addWidget(meta_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        groups: list[tuple[str, Sequence[Mapping[str, Any]]]] = []
        if isinstance(sources, Mapping):
            groups = [
                ("官方政策文件", sources.get("policy_documents") or []),
                ("官方平台入口", sources.get("official_portals") or []),
                ("辅助来源（第三方，非官方）", sources.get("third_party_sources") or []),
            ]

        for group_title, items in groups:
            title_label = QLabel(group_title)
            title_label.setObjectName("SectionTitle")
            content_layout.addWidget(title_label)
            for item in items:
                content_layout.addWidget(self._source_row(item))
            content_layout.addSpacing(6)

        if isinstance(sources, Mapping) and sources.get("disclaimer"):
            disclaimer = QLabel(str(sources["disclaimer"]))
            disclaimer.setObjectName("DisclaimerText")
            disclaimer.setWordWrap(True)
            content_layout.addWidget(disclaimer)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _source_row(self, item: Mapping[str, Any]) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title = QLabel(str(item.get("title") or "未命名来源"))
        title.setWordWrap(True)
        layout.addWidget(title)

        detail_parts = [
            str(item.get("publisher") or ""),
            str(item.get("published") or ""),
            str(item.get("note") or ""),
        ]
        detail = " · ".join(part for part in detail_parts if part)
        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("CardMeta")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

        url = str(item.get("url") or "")
        if url:
            link = QPushButton(url)
            link.setObjectName("LinkButton")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.clicked.connect(lambda: self.browser_service.open(url))
            layout.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)

        return row
