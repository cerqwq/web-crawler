@echo off
chcp 65001 >nul
title 一键爬虫 - 自动分类版

echo.
echo ========================================
echo       🕷️  一键爬虫 - 自动分类版
echo ========================================
echo.
echo   自动识别: 视频、音频、图片、文档
echo   双击运行，输入网址即可开始
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
pip install requests beautifulsoup4 -q
echo ✅ 依赖安装完成
echo.

REM 运行爬虫
python crawler_easy.py

pause
