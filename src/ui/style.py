"""界面样式（QSS）与配色。

不用传统 Windows 表格控件，改为现代卡片式布局：浅色背景 + 圆角卡片 +
克制的主题色，按钮用扁平描边样式，适合学生使用。
"""

from __future__ import annotations

#: 主题色
PRIMARY = "#2563eb"
PRIMARY_DARK = "#1d4ed8"
TEXT = "#1f2937"
TEXT_MUTED = "#6b7280"
BORDER = "#e5e7eb"
SURFACE = "#ffffff"
BACKGROUND = "#f6f7f9"
PUBLIC_TAG = "#0f766e"
PRIVATE_TAG = "#b45309"
WARN = "#b91c1c"

APP_STYLE = f"""
QWidget {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

#RootWidget, QMainWindow {{
    background: {BACKGROUND};
}}

/* ---------- 顶部栏 ---------- */
#HeaderBar {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
#AppTitle {{
    font-size: 19px;
    font-weight: 600;
    color: {TEXT};
}}
#DataYearBadge {{
    background: #e0edff;
    color: {PRIMARY_DARK};
    border-radius: 10px;
    padding: 2px 10px;
    font-weight: 600;
}}
#HeaderHint {{
    color: {TEXT_MUTED};
}}

/* ---------- 侧栏 ---------- */
#Sidebar {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}
#SidebarTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_MUTED};
    padding-top: 4px;
}}
QLineEdit, QComboBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER};
    background: {SURFACE};
    selection-background-color: #e0edff;
    selection-color: {TEXT};
    outline: none;
}}

/* 侧栏范围切换（全部/收藏/最近）*/
QPushButton#ScopeButton {{
    text-align: left;
    padding: 8px 12px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: {TEXT};
}}
QPushButton#ScopeButton:hover {{
    background: #f0f2f5;
}}
QPushButton#ScopeButton:checked {{
    background: #e0edff;
    color: {PRIMARY_DARK};
    font-weight: 600;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    border-radius: 8px;
    padding: 7px 14px;
    background: {SURFACE};
    border: 1px solid {BORDER};
}}
QPushButton:hover {{
    background: #f3f4f6;
}}
QPushButton:disabled {{
    color: #9ca3af;
    background: #f9fafb;
}}
QPushButton#PrimaryButton {{
    background: {PRIMARY};
    border: 1px solid {PRIMARY};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background: {PRIMARY_DARK};
}}
QPushButton#LinkButton {{
    border: none;
    background: transparent;
    color: {PRIMARY};
    text-decoration: underline;
    padding: 2px;
}}
QPushButton#FavoriteButton {{
    border: none;
    background: transparent;
    font-size: 16px;
    padding: 2px 6px;
    color: #9ca3af;
}}
QPushButton#FavoriteButton:checked {{
    color: #f59e0b;
}}

/* ---------- 卡片 ---------- */
#SchoolCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
#SchoolCard:hover {{
    border: 1px solid #c7d2fe;
}}
#CardTitle {{
    font-size: 15px;
    font-weight: 600;
}}
#CardMeta {{
    color: {TEXT_MUTED};
}}
#CardAddress {{
    color: {TEXT_MUTED};
}}
#CardDistance {{
    color: {PRIMARY_DARK};
    font-weight: 600;
}}
#PublicBadge {{
    color: {PUBLIC_TAG};
    background: #e6fffb;
    border-radius: 8px;
    padding: 1px 8px;
}}
#PrivateBadge {{
    color: {PRIVATE_TAG};
    background: #fff7e6;
    border-radius: 8px;
    padding: 1px 8px;
}}
#WarnBadge {{
    color: {WARN};
    background: #fee2e2;
    border-radius: 8px;
    padding: 1px 8px;
}}

/* ---------- 列表滚动区 ---------- */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1;
    border-radius: 5px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: #94a3b8;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ---------- 状态栏 / 弹窗 ---------- */
#StatusBar {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
}}
QDialog {{
    background: {BACKGROUND};
}}
#DetailTitle {{
    font-size: 18px;
    font-weight: 600;
}}
#FieldLabel {{
    color: {TEXT_MUTED};
}}
#FieldValue {{
    color: {TEXT};
}}
#DisclaimerText {{
    color: {TEXT_MUTED};
}}
"""
