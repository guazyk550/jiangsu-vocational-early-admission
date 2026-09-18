"""江苏高职提前招生院校导航器 —— 程序入口。

启动流程（刻意不阻塞、不强制联网）::

    QApplication
      → 加载本地 data/schools.json（立即显示）
      → 显示主窗口
      → 若配置了数据更新地址，才在后台线程静默检查更新
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from src.data.school_repository import SchoolRepository, project_root
from src.services.config_service import ConfigService
from src.services.favorites_service import FavoritesService, RecentService
from src.services.browser_service import BrowserService
from src.ui.main_window import MainWindow
from src.ui.style import build_palette, system_prefers_dark, theme_for

APP_NAME = "江苏高职提前招生院校导航器"
ORG_NAME = "JSVocNav"


def _icon_path() -> Path | None:
    """定位图标（打包后资源在 sys._MEIPASS 下）。"""
    candidates = [
        project_root() / "assets" / "icon.ico",
        project_root() / "assets" / "icon.png",
    ]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.insert(0, Path(bundle_dir) / "assets" / "icon.ico")
    for path in candidates:
        if path.exists():
            return path
    return None


def run_selftest(output_path: str) -> int:
    """自检模式：把数据加载诊断结果写入文件并退出。

    windowed exe 没有控制台，用户/维护者可以用它排查「exe 到底读了哪个数据文件」::

        江苏高职提前招生.exe --selftest selftest.txt
    """
    from src.data.school_repository import RepositoryError, candidate_data_files

    lines: list[str] = []
    lines.append(f"frozen = {getattr(sys, 'frozen', False)}")
    lines.append(f"executable = {sys.executable}")
    lines.append(f"_MEIPASS = {getattr(sys, '_MEIPASS', None)}")
    lines.append(f"project_root = {project_root()}")
    lines.append("")
    lines.append("候选数据文件（按优先级）：")
    for path in candidate_data_files():
        lines.append(f"  [{'存在' if path.exists() else '缺失'}] {path}")
    lines.append("")

    try:
        loaded = SchoolRepository().load()
        summary = {
            "source_path": loaded.source_path,
            "school_count": len(loaded.schools),
            "data_year": loaded.data_year,
            "last_verified": loaded.last_verified,
            "with_coordinates": sum(1 for s in loaded.schools if s.has_coordinates),
            "warnings": list(loaded.warnings)[:5],
        }
        lines.append("加载结果：")
        for key, value in summary.items():
            lines.append(f"  {key} = {value}")
        ok = True
    except RepositoryError as exc:
        lines.append(f"加载失败：{exc}")
        ok = False

    lines.append("")
    try:
        config = ConfigService().load()
        lines.append(f"update_url = {config.update_url!r}（为空表示启动时不联网）")
        lines.append(f"参照点 = {config.origin.name} {config.origin.latitude},{config.origin.longitude}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"配置读取失败：{exc}")

    try:
        lines.append(f"系统主题 = {theme_for(system_prefers_dark()).name}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"主题检测失败：{exc}")

    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        index = sys.argv.index("--selftest")
        target = (
            sys.argv[index + 1] if len(sys.argv) > index + 1 else "selftest.txt"
        )
        return run_selftest(target)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    # 先应用与系统一致的调色板，避免启动瞬间的浅色闪烁（QSS 由主窗口再叠加）
    app.setPalette(build_palette(theme_for(system_prefers_dark())))

    icon_path = _icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    try:
        repository = SchoolRepository()
        config_service = ConfigService()
        window = MainWindow(
            repository,
            config_service,
            favorites=FavoritesService(),
            recent=RecentService(),
            browser_service=BrowserService(),
        )
        if icon_path is not None:
            window.setWindowIcon(QIcon(str(icon_path)))
        window.show()
    except Exception:  # noqa: BLE001 - 启动期任何异常都要给用户一个说明，而不是黑屏退出
        QMessageBox.critical(
            None,
            APP_NAME,
            "程序启动失败：\n\n" + traceback.format_exc(limit=3),
        )
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
