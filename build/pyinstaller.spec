# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（单文件 EXE）。

用法（在项目根目录执行）::

    py -m PyInstaller --noconfirm --clean build/pyinstaller.spec

产物：``dist/江苏高职提前招生.exe``（双击即可运行，无需安装 Python）。

关键点
------
1. ``data/*.json`` 会被打包进 exe 作为**内置兜底数据**；
2. 程序运行时**优先读取 exe 同级的 ``data/schools.json``**，
   因此用户只要替换该文件即可更新院校数据，无需重新打包（见 README）；
3. 排除 QtWebEngine 等本项目完全用不到的重量级模块，控制体积。
"""

import os

# PyInstaller 注入的 SPECPATH 是「spec 文件所在目录」（此处为 <项目根>/build）
SPEC_DIR = os.path.abspath(SPECPATH)  # noqa: F821
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, os.pardir))

DATA_FILES = [
    (os.path.join(PROJECT_ROOT, "data", "schools.json"), "data"),
    (os.path.join(PROJECT_ROOT, "data", "sources.json"), "data"),
    (os.path.join(PROJECT_ROOT, "assets", "icon.ico"), "assets"),
    (os.path.join(PROJECT_ROOT, "assets", "icon.png"), "assets"),
]

# 本项目不使用这些模块，排除后 exe 体积可显著减小
EXCLUDES = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtHelp",
    "PySide6.QtDesigner",
    "PySide6.QtUiTools",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtTextToSpeech",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtStateMachine",
    "PySide6.QtSpatialAudio",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "shiboken6.support",
    "tkinter",
    "unittest",
    "pydoc_data",
    "lib2to3",
    "test",
]

a = Analysis(  # noqa: F821 - PyInstaller 注入
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=DATA_FILES,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="江苏高职提前招生",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 不启用 UPX：避免杀毒软件误报
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口（GUI 程序）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, "assets", "icon.ico"),
)
