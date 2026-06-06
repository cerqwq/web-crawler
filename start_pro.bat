@echo off
chcp 65001 >nul
title 一键爬虫 - 专业版（带Web界面）

echo.
echo ========================================
echo       🕷️  一键爬虫 - 专业版
echo ========================================
echo.
echo   功能: 自动分类 + Web实时监控
echo   界面: http://localhost:8088
echo.
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未安装Python
    echo.
    echo 请先安装Python: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM 安装依赖
echo 📦 正在安装依赖...
pip install requests beautifulsoup4 flask -q
echo ✅ 依赖安装完成
echo.

REM 运行爬虫
python crawler_pro.py

pause
