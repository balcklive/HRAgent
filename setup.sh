#!/bin/bash

# HR智能体简历筛选系统 - 快速设置脚本

set -e

echo "🚀 HR智能体简历筛选系统 - 快速设置"
echo "=================================="

# 检查Python版本
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "📋 检测到Python版本: $python_version"

if [[ $(echo $python_version | cut -d. -f1) -lt 3 ]] || [[ $(echo $python_version | cut -d. -f2) -lt 8 ]]; then
    echo "❌ 需要Python 3.8或更高版本"
    exit 1
fi

# 检查uv是否已安装
if ! command -v uv &> /dev/null; then
    echo "📦 uv未安装，正在安装..."
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows
        powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    else
        # macOS/Linux
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source $HOME/.cargo/env
    fi
    echo "✅ uv安装完成"
else
    echo "✅ uv已安装: $(uv --version)"
fi

# 创建虚拟环境并安装依赖
echo "📦 安装项目依赖..."
uv sync

# 生成锁定文件
echo "🔒 生成依赖锁定文件..."
uv lock

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "📝 创建环境变量文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，设置您的 OPENAI_API_KEY"
else
    echo "✅ 环境变量文件已存在"
fi

# 检查API密钥
if grep -q "your_openai_api_key_here" .env 2>/dev/null; then
    echo "⚠️  请在 .env 文件中设置您的真实 OPENAI_API_KEY"
fi

echo ""
echo "🎉 设置完成！"
echo ""
echo "📚 下一步："
echo "  1. 编辑 .env 文件，设置您的 OPENAI_API_KEY"
echo "  2. 运行测试: make test"
echo "  3. 运行示例: make run-example"
echo "  4. 交互式使用: make run-interactive"
echo ""
echo "💡 使用 'make help' 查看所有可用命令"
echo "📖 查看 README.md 获取详细文档"