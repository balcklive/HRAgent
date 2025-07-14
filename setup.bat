@echo off
setlocal enabledelayedexpansion

echo 🚀 HR智能体简历筛选系统 - 快速设置
echo ==================================

REM 检查Python版本
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set python_version=%%i
echo 📋 检测到Python版本: %python_version%

REM 检查uv是否已安装
uv --version >nul 2>&1
if errorlevel 1 (
    echo 📦 uv未安装，正在安装...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo ❌ uv安装失败
        pause
        exit /b 1
    )
    echo ✅ uv安装完成
) else (
    echo ✅ uv已安装
)

REM 创建虚拟环境并安装依赖
echo 📦 安装项目依赖...
uv sync
if errorlevel 1 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)

REM 生成锁定文件
echo 🔒 生成依赖锁定文件...
uv lock
if errorlevel 1 (
    echo ❌ 锁定文件生成失败
    pause
    exit /b 1
)

REM 检查环境变量文件
if not exist ".env" (
    echo 📝 创建环境变量文件...
    copy ".env.example" ".env"
    echo ⚠️  请编辑 .env 文件，设置您的 OPENAI_API_KEY
) else (
    echo ✅ 环境变量文件已存在
)

REM 检查API密钥
findstr "your_openai_api_key_here" .env >nul 2>&1
if not errorlevel 1 (
    echo ⚠️  请在 .env 文件中设置您的真实 OPENAI_API_KEY
)

echo.
echo 🎉 设置完成！
echo.
echo 📚 下一步：
echo   1. 编辑 .env 文件，设置您的 OPENAI_API_KEY
echo   2. 运行示例: uv run python main.py --jd examples/jd_example.txt --resumes examples/resume_example.txt
echo   3. 交互式使用: uv run python main.py --interactive
echo.
echo 💡 在Linux/macOS上可以使用 'make help' 查看所有可用命令
echo 📖 查看 README.md 获取详细文档

pause