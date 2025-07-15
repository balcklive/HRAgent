#!/bin/bash

# HR智能体测试脚本 - local_example

echo "🚀 HR智能体简历筛选系统测试 (PDF简历)"
echo "================================"

# 确定脚本位置并导航到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 检查uv是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ uv未安装，请先运行 ./setup.sh"
    exit 1
fi

# 检查.env文件
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "❌ .env文件不存在，请先设置环境变量"
    exit 1
fi

# 检查API Key
if grep -q "your_openai_api_key_here" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo "⚠️  请在 .env 文件中设置真实的 OPENAI_API_KEY"
    exit 1
fi

echo "📋 测试场景：AI研究工程师招聘"
echo "JD文件：examples/local_example/jd_researcher_engineer.txt"
echo "候选人简历 (PDF格式)："
echo "  - Ashba Sameed (MBZUAI经验，AI研究)"
echo "  - Kena Hemnani (GenAI简历)"
echo "  - Praveen Singh (技术简历)"
echo ""

read -p "🤔 是否开始测试？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "测试取消"
    exit 0
fi

echo "⏰ 开始测试...（这可能需要几分钟时间）"
echo "📄 正在解析PDF简历文件..."
echo ""

# 运行测试
cd "$PROJECT_ROOT" && uv run python main.py \
    --jd examples/local_example/jd_researcher_engineer.txt \
    --resumes \
        examples/local_example/Ashba_sameed.pdf \
        examples/local_example/Kena_Hemnani_resume_GenAI.pdf \
        examples/local_example/PRAVEEN_SINGH_RESUME.pdf

echo ""
echo "🎉 测试完成！"
echo "📊 查看生成的报告文件：candidate_evaluation_report_*.md"
echo ""
echo "💡 提示："
echo "  - 使用 'make run-interactive' 进行交互式测试"
echo "  - 查看 examples/local_example/ 目录了解更多PDF简历测试用例"
echo "  - PDF解析已集成到项目中，支持自动提取简历文本内容"