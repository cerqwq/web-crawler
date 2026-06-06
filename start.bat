@echo off
chcp 65001 >nul
echo ========================================
echo       一键爬虫 - 启动脚本
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未安装Python
    pause
    exit /b 1
)

REM 安装依赖
echo 正在安装依赖...
pip install -r requirements.txt -q
echo 依赖安装完成
echo.

REM 提示输入URL
set /p url="请输入要爬取的URL: "
if "%url%"=="" (
    echo 错误：URL不能为空
    pause
    exit /b 1
)

REM 选择模式
echo.
echo 选择模式：
echo 1. 快速模式（100页面，深度2）
echo 2. 标准模式（500页面，深度3）
echo 3. 完整模式（1000页面，深度4）
echo 4. 自定义模式
echo.
set /p mode="请选择 (1-4): "

if "%mode%"=="1" (
    set params=-d 2 -p 100 -w 3
) else if "%mode%"=="2" (
    set params=-d 3 -p 500 -w 5
) else if "%mode%"=="3" (
    set params=-d 4 -p 1000 -w 8
) else if "%mode%"=="4" (
    set /p depth="最大深度: "
    set /p pages="最大页面数: "
    set /p workers="线程数: "
    set params=-d %depth% -p %pages% -w %workers%
) else (
    set params=-d 3 -p 500 -w 5
)

REM 启动爬虫
echo.
echo 启动爬虫...
echo URL: %url%
echo 参数: %params%
echo.

python crawler.py %url% %params% --json --csv --db -o ./output

echo.
echo 爬取完成！结果保存在 ./output 目录
pause
