#!/bin/bash

# HR智能体测试脚本

echo "🚀 HR智能体简历筛选系统测试"
echo "================================"

# 检查uv是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ uv未安装，请先运行 ./setup.sh"
    exit 1
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "❌ .env文件不存在，请先设置环境变量"
    exit 1
fi

# 检查API Key
if grep -q "your_openai_api_key_here" .env 2>/dev/null; then
    echo "⚠️  请在 .env 文件中设置真实的 OPENAI_API_KEY"
    exit 1
fi

echo "📋 测试场景：后端工程师招聘"
echo "JD文件：examples/jd_backend_engineer.txt"
echo "候选人简历："
echo "  - 李明 (8年经验，字节跳动)"
echo "  - 王小红 (2年经验，腾讯新人)"  
echo "  - 张志强 (12年经验，微软架构师)"
echo "  - 刘洋 (2年经验，小公司)"
echo "  - 陈思雨 (6年经验，蚂蚁集团)"
echo ""

read -p "🤔 是否开始测试？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "测试取消"
    exit 0
fi

echo "⏰ 开始测试...（这可能需要几分钟时间）"
echo ""

# 运行测试
uv run python main.py \
    --jd examples/jd_backend_engineer.txt \
    --resumes \
        examples/resume_candidate_a.txt \
        examples/resume_candidate_b.txt \
        examples/resume_candidate_c.txt \
        examples/resume_candidate_d.txt \
        examples/resume_candidate_e.txt

echo ""
echo "🎉 测试完成！"
echo "📊 查看生成的报告文件：candidate_evaluation_report_*.md"
echo ""
echo "💡 提示："
echo "  - 使用 'make run-interactive' 进行交互式测试"
echo "  - 查看 examples/ 目录了解更多测试用例"