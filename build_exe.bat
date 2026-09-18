@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   江苏高职提前招生院校导航器 - 一键打包 EXE
echo ============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python 启动器 py。
    echo        请先安装 Python 3.12 或更高版本，安装时勾选 "Add python.exe to PATH"。
    pause
    exit /b 1
)

echo [1/4] 安装/检查依赖（PySide6、PyInstaller）...
py -m pip install -r requirements.txt || goto :fail

echo.
echo [2/4] 生成应用图标...
py tools\make_icon.py || goto :fail

echo.
echo [3/4] 数据体检（有 ERROR 会中止）...
py tools\validate_data.py || goto :fail

echo.
echo [4/4] 打包为单文件 EXE（首次约 1-3 分钟）...
py -m PyInstaller --noconfirm --clean build\pyinstaller.spec || goto :fail

echo.
echo ============================================================
echo  打包完成！
echo    产物：dist\江苏高职提前招生.exe
echo.
echo  发布给用户时建议同时提供：
echo    dist\江苏高职提前招生.exe
echo    data\schools.json   （放在 exe 同级的 data 目录下可覆盖内置数据）
echo ============================================================
pause
exit /b 0

:fail
echo.
echo [失败] 上一步出错，请查看上方日志。
pause
exit /b 1
