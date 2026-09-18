"""界面主题（浅色 / 深色）与样式表生成。

为什么要两套主题
----------------
之前只有一套浅色配色，并用 **固定** 深色文字（如 ``#6b7280``）。当 Windows 处于
深色模式时，Qt 会给未显式设置背景的控件（对话框内容区、滚动视口等）套上系统深色
背景，于是出现「黑底 + 深灰/深蓝字」看不清的问题。

本模块的做法：

1. 把颜色抽成 :class:`Theme` 设计令牌，提供 ``LIGHT_THEME`` / ``DARK_THEME`` 两套；
2. 由令牌同时生成 **QSS** 和 **QPalette**——QSS 只覆盖需要精细化控制的控件，
   QPalette 负责兜底（让所有未被 QSS 触及的控件也协调）；
3. 跟随系统主题：``system_prefers_dark()`` 读取 Qt 的 ``QStyleHints.colorScheme()``，
   主窗口监听 ``colorSchemeChanged`` 后重新应用主题。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


@dataclass(frozen=True, slots=True)
class Theme:
    """一套配色令牌。"""

    name: str
    dark: bool
    background: str  # 窗口底色
    surface: str  # 卡片 / 侧栏 / 顶栏底色
    surface_alt: str  # 次级面（hover、输入框等）
    text: str  # 主文字
    text_muted: str  # 次要文字（免责声明、字段标签等）
    border: str
    primary: str  # 主色（按钮底色）
    primary_hover: str  # 主色 hover（仍保证白字对比度）
    primary_strong: str  # 主色强调文字（浅色下更深、深色下更亮）
    primary_soft: str  # 主色浅底（选中项、年份徽标）
    hover: str
    disabled_text: str
    disabled_bg: str
    public_fg: str
    public_bg: str
    private_fg: str
    private_bg: str
    warn_fg: str
    warn_bg: str
    scroll: str
    scroll_hover: str
    link: str


LIGHT_THEME = Theme(
    name="浅色",
    dark=False,
    background="#f6f7f9",
    surface="#ffffff",
    surface_alt="#f3f4f6",
    text="#1f2937",
    text_muted="#6b7280",
    border="#e5e7eb",
    primary="#2563eb",
    primary_hover="#1d4ed8",
    primary_strong="#1d4ed8",
    primary_soft="#e0edff",
    hover="#f0f2f5",
    disabled_text="#9ca3af",
    disabled_bg="#f9fafb",
    public_fg="#0f766e",
    public_bg="#e6fffb",
    private_fg="#b45309",
    private_bg="#fff7e6",
    warn_fg="#b91c1c",
    warn_bg="#fee2e2",
    scroll="#cbd5e1",
    scroll_hover="#94a3b8",
    link="#2563eb",
)

DARK_THEME = Theme(
    name="深色",
    dark=True,
    background="#15171c",
    surface="#1e2128",
    surface_alt="#262a33",
    text="#e6e8ec",
    text_muted="#a3adbb",  # 深色下必须比浅色主题更亮，否则读不清
    border="#333844",
    primary="#2563eb",
    primary_hover="#1d4ed8",
    primary_strong="#93c5fd",  # 深色下强调文字必须更亮才看得清
    primary_soft="#1c355f",
    hover="#242833",
    disabled_text="#6b7280",
    disabled_bg="#1b1e24",
    public_fg="#4ade80",
    public_bg="#14311f",
    private_fg="#fbbf24",
    private_bg="#3a2c12",
    warn_fg="#fca5a5",
    warn_bg="#3d1d1d",
    scroll="#3f4652",
    scroll_hover="#5b6473",
    link="#93c5fd",
)


def system_prefers_dark() -> bool:
    """系统是否使用深色模式（Qt 6.5+ 的 colorScheme；无法判断时按浅色处理）。"""
    try:
        hints = QGuiApplication.styleHints()
        return hints.colorScheme() == Qt.ColorScheme.Dark
    except Exception:  # noqa: BLE001 - 旧版本或异常平台回退浅色
        return False


def theme_for(dark: bool) -> Theme:
    return DARK_THEME if dark else LIGHT_THEME


def build_palette(theme: Theme) -> QPalette:
    """与主题一致的调色板，负责兜住 QSS 没覆盖到的控件。

    这是修「黑底深字」的关键：未显式设色的控件会使用这里的 Window/Base 颜色，
    不会再回落成系统深色背景。
    """
    palette = QPalette()
    window = QColor(theme.background)
    surface = QColor(theme.surface)
    text = QColor(theme.text)
    muted = QColor(theme.text_muted)
    primary = QColor(theme.primary)

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, surface)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.surface_alt))
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, muted)
    palette.setColor(QPalette.ColorRole.Button, surface)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.ToolTipBase, surface)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Highlight, primary)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor(theme.link))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))

    disabled = QPalette.ColorGroup.Disabled
    palette.setColor(disabled, QPalette.ColorRole.Text, QColor(theme.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.ButtonText, QColor(theme.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.WindowText, QColor(theme.disabled_text))
    return palette


def build_stylesheet(theme: Theme) -> str:
    """由主题令牌生成 QSS。

    注意：所有会承载文字的表面都在这里显式设置了 ``background``，
    避免任何控件在深色系统下露出系统底色。
    """
    t = theme
    return f"""
QWidget {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    color: {t.text};
}}

QMainWindow, #RootWidget {{
    background: {t.background};
}}

/* ---------- 顶部栏 ---------- */
#HeaderBar {{
    background: {t.surface};
    border-bottom: 1px solid {t.border};
}}
#AppTitle {{
    font-size: 19px;
    font-weight: 600;
    color: {t.text};
}}
#DataYearBadge {{
    background: {t.primary_soft};
    color: {t.primary_strong};
    border-radius: 10px;
    padding: 2px 10px;
    font-weight: 600;
}}
#HeaderHint {{
    color: {t.text_muted};
}}

/* ---------- 侧栏 ---------- */
#Sidebar {{
    background: {t.surface};
    border-right: 1px solid {t.border};
}}
#SidebarTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {t.text_muted};
    padding-top: 4px;
}}
QLineEdit, QComboBox {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 8px;
    padding: 7px 10px;
    color: {t.text};
    selection-background-color: {t.primary};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {t.primary};
}}
QLineEdit::placeholder {{
    color: {t.text_muted};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {t.border};
    background: {t.surface};
    color: {t.text};
    selection-background-color: {t.primary_soft};
    selection-color: {t.text};
    outline: none;
}}

/* 侧栏范围切换（全部/收藏/最近）*/
QPushButton#ScopeButton {{
    text-align: left;
    padding: 8px 12px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: {t.text};
}}
QPushButton#ScopeButton:hover {{
    background: {t.hover};
}}
QPushButton#ScopeButton:checked {{
    background: {t.primary_soft};
    color: {t.primary_strong};
    font-weight: 600;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    border-radius: 8px;
    padding: 7px 14px;
    background: {t.surface};
    border: 1px solid {t.border};
    color: {t.text};
}}
QPushButton:hover {{
    background: {t.hover};
}}
QPushButton:pressed {{
    background: {t.surface_alt};
}}
QPushButton:disabled {{
    color: {t.disabled_text};
    background: {t.disabled_bg};
    border: 1px solid {t.border};
}}
QPushButton#PrimaryButton {{
    background: {t.primary};
    border: 1px solid {t.primary};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background: {t.primary_hover};
    border: 1px solid {t.primary_hover};
}}
QPushButton#PrimaryButton:disabled {{
    background: {t.disabled_bg};
    border: 1px solid {t.border};
    color: {t.disabled_text};
}}
QPushButton#LinkButton {{
    border: none;
    background: transparent;
    color: {t.link};
    text-decoration: underline;
    padding: 2px;
    text-align: left;
}}
QPushButton#LinkButton:hover {{
    color: {t.primary_strong};
    background: transparent;
}}
QPushButton#FavoriteButton {{
    border: none;
    background: transparent;
    font-size: 16px;
    padding: 2px 6px;
    color: {t.text_muted};
}}
QPushButton#FavoriteButton:checked {{
    color: #f59e0b;
}}

/* ---------- 卡片 ---------- */
#SchoolCard {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 12px;
}}
#SchoolCard:hover {{
    border: 1px solid {t.primary};
}}
#CardTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {t.text};
}}
#CardMeta {{
    color: {t.text_muted};
}}
#CardAddress {{
    color: {t.text_muted};
}}
#CardDistance {{
    color: {t.primary_strong};
    font-weight: 600;
}}
#PublicBadge {{
    color: {t.public_fg};
    background: {t.public_bg};
    border-radius: 8px;
    padding: 1px 8px;
}}
#PrivateBadge {{
    color: {t.private_fg};
    background: {t.private_bg};
    border-radius: 8px;
    padding: 1px 8px;
}}
#WarnBadge {{
    color: {t.warn_fg};
    background: {t.warn_bg};
    border-radius: 8px;
    padding: 1px 8px;
}}

/* ---------- 滚动区 ---------- */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t.scroll};
    border-radius: 5px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t.scroll_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ---------- 状态栏 / 弹窗 ---------- */
#StatusBar {{
    background: {t.surface};
    border-top: 1px solid {t.border};
    color: {t.text_muted};
}}
QDialog {{
    background: {t.background};
}}
/* 对话框内的滚动内容区：显式给底色，杜绝深色系统下的黑底 */
QDialog QScrollArea, QDialog QScrollArea > QWidget > QWidget {{
    background: {t.background};
}}
#DetailTitle {{
    font-size: 18px;
    font-weight: 600;
    color: {t.text};
}}
#SectionTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {t.text_muted};
    padding-top: 4px;
}}
#Separator {{
    border: none;
    background: {t.border};
    min-height: 1px;
    max-height: 1px;
}}
#FieldLabel {{
    color: {t.text_muted};
}}
#FieldValue {{
    color: {t.text};
}}
#DisclaimerText {{
    color: {t.text_muted};
}}
#SourceTitle {{
    color: {t.text};
}}
QMessageBox {{
    background: {t.surface};
}}
QMessageBox QLabel {{
    color: {t.text};
}}
QToolTip {{
    background: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    padding: 4px 6px;
}}
"""
