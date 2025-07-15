#!/usr/bin/env python3
"""
HR智能体简历筛选系统 - 主应用程序

使用方法:
  python main.py --jd jd.txt --resumes resume1.pdf resume2.docx resume3.txt
  python main.py --interactive
"""

import argparse
import asyncio
import os
import sys
from typing import List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.workflow_optimized import HRAgentWorkflow
from src.nodes import (
    RequirementConfirmationNode, 
    ScoringDimensionNode,
    ResumeStructureNode,
    CandidateEvaluationNode,
    ReportGenerationNode
)
from src.models import JobRequirement, ScoringDimensions, ScoringDimension

class HRAgentApp:
    """HR智能体主应用程序"""
    
    def __init__(self):
        self.workflow = HRAgentWorkflow()
        
    async def run_full_workflow(self, jd_file: str, resume_files: List[str]):
        """运行完整工作流"""
        try:
            # 读取JD文件
            if not os.path.exists(jd_file):
                print(f"❌ JD文件不存在: {jd_file}")
                return
            
            with open(jd_file, 'r', encoding='utf-8') as f:
                jd_text = f.read()
            
            print(f"📄 JD文件: {jd_file}")
            print(f"📋 简历文件数量: {len(resume_files)}")
            
            # 运行工作流
            result = await self.workflow.run_workflow(jd_text, resume_files)
            
            print(f"\n✅ 执行完成！")
            print(f"📊 最终报告已保存至: {result.get('report_file', '未保存')}")
            
            return result
            
        except Exception as e:
            print(f"❌ 执行失败: {str(e)}")
            return None
    
    def run_interactive_mode(self):
        """交互式模式"""
        print("=== HR智能体简历筛选系统 (交互式模式) ===")
        print("请选择要运行的功能:")
        print("1. 需求确认 (单独运行)")
        print("2. 简历结构化 (单独运行)")
        print("3. 完整工作流")
        print("4. 退出")
        
        while True:
            choice = input("\n请选择 (1-4): ").strip()
            
            if choice == "1":
                self._run_requirement_confirmation()
            elif choice == "2":
                asyncio.run(self._run_resume_structure())
            elif choice == "3":
                asyncio.run(self._run_interactive_workflow())
            elif choice == "4":
                print("再见！")
                break
            else:
                print("无效选择，请重试")
    
    def _run_requirement_confirmation(self):
        """运行需求确认"""
        print("\n=== 需求确认 ===")
        jd_text = input("请输入JD文本 (或文件路径): ").strip()
        
        # 检查是否是文件路径
        if os.path.exists(jd_text):
            with open(jd_text, 'r', encoding='utf-8') as f:
                jd_text = f.read()
        
        if not jd_text:
            print("❌ JD文本不能为空")
            return
        
        # 运行需求确认
        node = RequirementConfirmationNode()
        job_requirement = node.run_standalone(jd_text)
        
        print(f"\n✅ 需求确认完成:")
        print(f"职位: {job_requirement.position}")
        print(f"必要条件: {job_requirement.must_have}")
        print(f"加分条件: {job_requirement.nice_to_have}")
        print(f"排除条件: {job_requirement.deal_breaker}")
    
    async def _run_resume_structure(self):
        """运行简历结构化"""
        print("\n=== 简历结构化 ===")
        resume_files_input = input("请输入简历文件路径 (多个文件用空格分隔): ").strip()
        
        if not resume_files_input:
            print("❌ 简历文件路径不能为空")
            return
        
        resume_files = resume_files_input.split()
        
        # 运行简历结构化
        node = ResumeStructureNode()
        profiles = await node.run_standalone(resume_files)
        
        print(f"\n✅ 简历结构化完成，处理了 {len(profiles)} 个候选人")
    
    async def _run_interactive_workflow(self):
        """运行交互式工作流"""
        print("\n=== 完整工作流 ===")
        
        # 输入JD
        jd_input = input("请输入JD文本或文件路径: ").strip()
        if not jd_input:
            print("❌ JD不能为空")
            return
        
        # 检查是否是文件路径
        if os.path.exists(jd_input):
            with open(jd_input, 'r', encoding='utf-8') as f:
                jd_text = f.read()
        else:
            jd_text = jd_input
        
        # 输入简历文件
        resume_files_input = input("请输入简历文件路径 (多个文件用空格分隔): ").strip()
        if not resume_files_input:
            print("❌ 简历文件路径不能为空")
            return
        
        resume_files = resume_files_input.split()
        
        # 运行工作流
        result = await self.workflow.run_workflow(jd_text, resume_files)
        
        if result:
            print(f"✅ 工作流执行成功！")
            print(f"📊 报告文件: {result.get('report_file', '未保存')}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="HR智能体简历筛选系统")
    parser.add_argument("--jd", help="JD文件路径")
    parser.add_argument("--resumes", nargs="+", help="简历文件路径列表")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")
    
    args = parser.parse_args()
    
    app = HRAgentApp()
    
    if args.interactive:
        # 交互式模式
        app.run_interactive_mode()
    elif args.jd and args.resumes:
        # 命令行模式
        asyncio.run(app.run_full_workflow(args.jd, args.resumes))
    else:
        # 显示帮助
        print("HR智能体简历筛选系统")
        print("\n使用方法:")
        print("  python main.py --jd jd.txt --resumes resume1.pdf resume2.docx")
        print("  python main.py --interactive")
        print("\n安装依赖:")
        print("  uv sync  # 创建虚拟环境并安装依赖")
        print("  或者 uv pip install -e .  # 安装到当前环境")
        print("\n环境变量配置:")
        print("  OPENAI_API_KEY: OpenAI API密钥")
        print("  OPENAI_MODEL: 模型名称 (默认: gpt-4o-mini)")
        
        # 检查环境变量
        if not os.getenv("OPENAI_API_KEY"):
            print("\n⚠️  请先设置 OPENAI_API_KEY 环境变量")
            print("   export OPENAI_API_KEY=your_api_key_here")
            print("   或者创建 .env 文件并添加 OPENAI_API_KEY=your_api_key_here")


if __name__ == "__main__":
    main()