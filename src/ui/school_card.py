"""院校卡片控件（列表中的一项）。

每个卡片展示：校名 / 城市·办学性质 / 地址 / 直线距离 / 操作按钮 + 收藏。
按钮策略（卡片上不放太多，避免拥挤；完整入口在详情页）：

- 主按钮：提前招生简章 / 提前招生栏目 / 打开招生网（逐级回退）；
- 招生计划：仅当该校有招生计划页时出现；
- 百度地图 / 查看详情。

所有交互都通过信号抛给主窗口处理，卡片本身不直接打开浏览器。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.school import OWNERSHIP_PUBLIC, School

MAX_ADDRESS_CHARS = 64


def _elide(text: str, limit: int = MAX_ADDRESS_CHARS) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class SchoolCard(QFrame):
    """单个院校卡片。"""

    openAdmissionRequested = Signal(object)
    openExternalRequested = Signal(object, str)  # (school, url)：打开任意收录链接
    openMapRequested = Signal(object)
    detailRequested = Signal(object)
    favoriteToggled = Signal(object)
    officialSiteRequested = Signal(object)

    def __init__(
        self,
        school: School,
        *,
        distance_text: str = "",
        is_favorite: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.school = school
        self.setObjectName("SchoolCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        # ---------------- 第一行：校名 + 收藏 ----------------
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        name_label = QLabel(school.name)
        name_label.setObjectName("CardTitle")
        name_label.setWordWrap(True)
        title_row.addWidget(name_label, 1)

        self.favorite_button = QPushButton("★" if is_favorite else "☆")
        self.favorite_button.setObjectName("FavoriteButton")
        self.favorite_button.setCheckable(True)
        self.favorite_button.setChecked(is_favorite)
        self.favorite_button.setToolTip("收藏该院校")
        self.favorite_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_button.clicked.connect(
            lambda: self.favoriteToggled.emit(self.school)
        )
        title_row.addWidget(self.favorite_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(title_row)

        # ---------------- 第二行：城市 · 办学性质 · 类型 ----------------
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        city_label = QLabel(school.city or "城市未知")
        city_label.setObjectName("CardMeta")
        meta_row.addWidget(city_label)

        meta_row.addWidget(self._ownership_badge(school))

        if school.school_type:
            type_label = QLabel(school.school_type)
            type_label.setObjectName("CardMeta")
            meta_row.addWidget(type_label)

        if school.early_admission_third_party:
            hint = QLabel("简章为第三方转载")
            hint.setObjectName("WarnBadge")
            hint.setToolTip(
                "该校未能核验到学校自有域名的提前招生页面，"
                "此处链接为公开网站的转载页，仅供参考"
            )
            meta_row.addWidget(hint)

        meta_row.addStretch(1)

        if distance_text:
            distance_label = QLabel(f"距目标校 {distance_text}")
            distance_label.setObjectName("CardDistance")
            distance_label.setToolTip("直线距离，非驾车距离")
            meta_row.addWidget(distance_label)

        root.addLayout(meta_row)

        # ---------------- 地址 ----------------
        address_label = QLabel(_elide(school.address) if school.address else "地址暂无数据")
        address_label.setObjectName("CardAddress")
        address_label.setWordWrap(True)
        root.addWidget(address_label)

        # ---------------- 操作按钮 ----------------
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        entry_url, entry_label = school.admission_entry
        admission_button = QPushButton(entry_label)
        admission_button.setObjectName("PrimaryButton")
        admission_button.setEnabled(bool(entry_url))
        admission_button.setCursor(Qt.CursorShape.PointingHandCursor)
        if not entry_url:
            admission_button.setToolTip("该校未收录到可用链接")
        elif school.early_admission_title:
            admission_button.setToolTip(school.early_admission_title)
        admission_button.clicked.connect(
            lambda: self.openExternalRequested.emit(self.school, entry_url)
        )
        button_row.addWidget(admission_button)

        if school.has_plan:
            plan_button = QPushButton("招生计划")
            plan_button.setCursor(Qt.CursorShape.PointingHandCursor)
            plan_button.setToolTip(school.admission_plan_title or "打开该校招生计划页面")
            plan_button.clicked.connect(
                lambda: self.openExternalRequested.emit(
                    self.school, school.admission_plan_url
                )
            )
            button_row.addWidget(plan_button)

        if school.has_brochure:
            brochure_button = QPushButton("招生简章")
            brochure_button.setCursor(Qt.CursorShape.PointingHandCursor)
            brochure_button.setToolTip(
                school.admission_brochure_title or "打开该校招生简章/章程"
            )
            brochure_button.clicked.connect(
                lambda: self.openExternalRequested.emit(
                    self.school, school.admission_brochure_url
                )
            )
            button_row.addWidget(brochure_button)

        map_button = QPushButton("百度地图")
        map_button.setCursor(Qt.CursorShape.PointingHandCursor)
        map_button.setToolTip("在百度地图中查看该校位置，并规划从参照点到该校的驾车路线")
        map_button.clicked.connect(lambda: self.openMapRequested.emit(self.school))
        button_row.addWidget(map_button)

        detail_button = QPushButton("查看详情")
        detail_button.setCursor(Qt.CursorShape.PointingHandCursor)
        detail_button.clicked.connect(lambda: self.detailRequested.emit(self.school))
        button_row.addWidget(detail_button)

        button_row.addStretch(1)
        root.addLayout(button_row)

    # ------------------------------------------------------------------ 辅助
    @staticmethod
    def _ownership_badge(school: School) -> QLabel:
        text = school.ownership or "性质未知"
        if school.ownership_note:
            text = f"{text}（{school.ownership_note}）"
        badge = QLabel(text)
        badge.setObjectName(
            "PublicBadge" if school.ownership == OWNERSHIP_PUBLIC else "PrivateBadge"
        )
        return badge

    def set_favorite(self, value: bool) -> None:
        self.favorite_button.setChecked(value)
        self.favorite_button.setText("★" if value else "☆")
