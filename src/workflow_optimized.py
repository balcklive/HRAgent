import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from src.workflow import HRAgentWorkflow
from src.nodes import (
    RequirementConfirmationNode,
    ScoringDimensionNode,
    ResumeStructureNode,
    CandidateEvaluationNode,
    ReportGenerationNode
)
from src.models import RequirementConfirmationState
from datetime import datetime
import os

class OptimizedHRAgentWorkflow:
    """异步优化HR智能体工作流"""
    
    def __init__(self, max_concurrent_resumes: int = 10, max_concurrent_evaluations: int = 8):
        self.requirement_node = RequirementConfirmationNode()
        self.dimension_node = ScoringDimensionNode()
        self.resume_node = ResumeStructureNode(max_concurrent=max_concurrent_resumes)
        self.evaluation_node = CandidateEvaluationNode(max_concurrent=max_concurrent_evaluations)
        self.report_node = ReportGenerationNode()
        
    async def run_web_workflow(self, job_requirement, resume_files: List[str]) -> Dict[str, Any]:
        """运行Web版工作流（跳过交互式需求确认）"""
        print("=== 🚀 HR智能体简历筛选系统 (Web版) ===")
        print(f"职位: {job_requirement.position}")
        print(f"简历文件数量: {len(resume_files)} 个")
        
        # 验证简历文件
        existing_files = [f for f in resume_files if os.path.exists(f)]
        
        if not existing_files:
            raise ValueError("没有有效的简历文件")
        
        start_time = time.time()
        print(f"⏱️ 开始时间: {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            # 步骤1: 简历处理（跳过需求确认）
            print("\n=== 📋 步骤1: 简历处理 ===")
            candidate_profiles = await self._handle_resume_processing(existing_files)
            
            # 步骤2: 生成评分维度
            print("\n=== 📊 步骤2: 生成评分维度 ===")
            step2_start = time.time()
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.dimension_node.process, job_requirement
            )
            if result["status"] != "success":
                raise ValueError(f"评分维度生成失败: {result['error']}")
            
            scoring_dimensions = result["scoring_dimensions"]
            print(f"✅ 评分维度生成成功，耗时: {time.time() - step2_start:.1f}秒")
            
            # 步骤3: 候选人评分
            print("\n=== 🎯 步骤3: 候选人评分 ===")
            step3_start = time.time()
            
            result = await self.evaluation_node.process(
                candidate_profiles, job_requirement, scoring_dimensions
            )
            if result["status"] != "success":
                raise ValueError(f"候选人评分失败: {result['error']}")
            
            evaluations = result["evaluations"]
            print(f"✅ 候选人评分完成，耗时: {time.time() - step3_start:.1f}秒")
            
            # 步骤4: 生成报告
            print("\n=== 📈 步骤4: 生成评估报告 ===")
            step4_start = time.time()
            
            result = self.report_node.process(evaluations, job_requirement, scoring_dimensions)
            if result["status"] != "success":
                raise ValueError(f"报告生成失败: {result['error']}")
            
            # 保存报告
            report = result["report"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"candidate_evaluation_report_web_{timestamp}.md"
            saved_file = self.report_node.save_report(report, filename)
            
            total_duration = time.time() - start_time
            print(f"\n🎉 Web工作流完成！总耗时: {total_duration:.1f}秒")
            
            return {
                "evaluations": evaluations,
                "final_report": report,
                "report_file": saved_file,
                "job_requirement": job_requirement,
                "scoring_dimensions": scoring_dimensions,
                "total_duration": total_duration
            }
            
        except Exception as e:
            print(f"\n❌ Web工作流执行失败: {str(e)}")
            raise

    async def run_web_workflow_stream(self, job_requirement, resume_files: List[str], 
                                     progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """运行Web版工作流（带进度流式输出）"""
        if progress_callback:
            await progress_callback({
                "stage": "initialization",
                "message": f"开始处理职位: {job_requirement.position}",
                "progress": 0,
                "total_items": len(resume_files),
                "completed_items": 0
            })
        
        # 验证简历文件
        existing_files = [f for f in resume_files if os.path.exists(f)]
        
        if not existing_files:
            raise ValueError("没有有效的简历文件")
        
        start_time = time.time()
        
        try:
            # 步骤1: 简历处理（带进度）
            if progress_callback:
                await progress_callback({
                    "stage": "resume_processing",
                    "message": "开始处理简历文件",
                    "progress": 10,
                    "total_items": len(existing_files),
                    "completed_items": 0
                })
            
            candidate_profiles = await self._handle_resume_processing_stream(existing_files, progress_callback)
            
            # 步骤2: 生成评分维度
            if progress_callback:
                await progress_callback({
                    "stage": "dimension_generation",
                    "message": "生成评分维度",
                    "progress": 40,
                    "total_items": 1,
                    "completed_items": 0
                })
            
            scoring_dimensions = await self._handle_dimension_generation_stream(job_requirement, progress_callback)
            
            # 步骤3: 候选人评估
            if progress_callback:
                await progress_callback({
                    "stage": "candidate_evaluation",
                    "message": "开始候选人评估",
                    "progress": 60,
                    "total_items": len(candidate_profiles),
                    "completed_items": 0
                })
            
            evaluation_result = await self._handle_candidate_evaluation_stream(
                candidate_profiles, job_requirement, scoring_dimensions, progress_callback
            )
            
            # 步骤4: 报告生成
            if progress_callback:
                await progress_callback({
                    "stage": "report_generation",
                    "message": "生成候选人评估报告",
                    "progress": 90,
                    "total_items": 1,
                    "completed_items": 0
                })
            
            report_result = await self._handle_report_generation_stream(
                evaluation_result, job_requirement, scoring_dimensions, progress_callback
            )
            
            # 完成
            if progress_callback:
                await progress_callback({
                    "stage": "complete",
                    "message": "处理完成",
                    "progress": 100,
                    "total_items": len(resume_files),
                    "completed_items": len(resume_files)
                })
            
            return report_result
            
        except Exception as e:
            if progress_callback:
                await progress_callback({
                    "stage": "error",
                    "message": f"处理出错: {str(e)}",
                    "progress": 0,
                    "error": str(e)
                })
            raise

    async def run_optimized_workflow(self, jd_text: str, resume_files: List[str]) -> Dict[str, Any]:
        """运行简化优化版工作流"""
        print("=== 🚀 HR智能体简历筛选系统 (异步优化版) ===")
        print(f"JD文本长度: {len(jd_text)} 字符")
        print(f"简历文件数量: {len(resume_files)} 个")
        print("✨ 启用并行处理优化")
        
        # 验证简历文件
        existing_files = [f for f in resume_files if os.path.exists(f)]
        
        if not existing_files:
            raise ValueError("没有有效的简历文件")
        
        start_time = time.time()
        print(f"⏱️ 开始时间: {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            # 步骤1: 并行执行需求确认和简历处理
            print("\n=== 🚀 步骤1: 启动并行处理 ===")
            print("同时进行需求确认和简历解析...")
            
            # 创建并行任务
            requirement_task = self._handle_requirement_confirmation(jd_text)
            resume_task = self._handle_resume_processing(existing_files)
            
            # 并行执行
            requirement_result, resume_result = await asyncio.gather(
                requirement_task, resume_task, return_exceptions=True
            )
            
            # 处理并行结果
            if isinstance(requirement_result, Exception):
                raise requirement_result
            if isinstance(resume_result, Exception):
                raise resume_result
            
            job_requirement = requirement_result
            candidate_profiles = resume_result
            
            parallel_duration = time.time() - start_time
            print(f"✅ 并行处理完成，耗时: {parallel_duration:.1f}秒")
            
            # 步骤2: 生成评分维度 (异步优化)
            print("\n=== 📊 步骤2: 生成评分维度 (异步优化) ===")
            step2_start = time.time()
            
            # 异步调用评分维度生成
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.dimension_node.process, job_requirement
            )
            if result["status"] != "success":
                raise ValueError(f"评分维度生成失败: {result['error']}")
            
            scoring_dimensions = result["scoring_dimensions"]
            print(f"✅ 评分维度生成成功，耗时: {time.time() - step2_start:.1f}秒")
            print(f"生成了 {len(scoring_dimensions.dimensions)} 个评分维度")
            
            # 步骤3: 候选人评分 (超级并发优化)
            print("\n=== 🎯 步骤3: 候选人评分 (超级并发优化) ===")
            step3_start = time.time()
            
            # 动态调整并发数以提升性能
            enhanced_evaluation_node = CandidateEvaluationNode(
                max_concurrent=min(12, len(candidate_profiles) * 2)
            )
            result = await enhanced_evaluation_node.process(
                candidate_profiles, job_requirement, scoring_dimensions
            )
            if result["status"] != "success":
                raise ValueError(f"候选人评分失败: {result['error']}")
            
            evaluations = result["evaluations"]
            print(f"✅ 候选人评分完成，耗时: {time.time() - step3_start:.1f}秒")
            print(f"成功评分 {len(evaluations)} 个候选人")
            
            # 显示排名
            print("\n候选人排名:")
            for eval in evaluations[:5]:
                print(f"{eval.ranking}. {eval.candidate_name} - {eval.overall_score:.1f}/10")
            
            # 步骤4: 生成报告
            print("\n=== 📈 步骤4: 生成评估报告 ===")
            step4_start = time.time()
            
            result = self.report_node.process(evaluations, job_requirement, scoring_dimensions)
            if result["status"] != "success":
                raise ValueError(f"报告生成失败: {result['error']}")
            
            # 保存报告
            report = result["report"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"candidate_evaluation_report_optimized_{timestamp}.md"
            saved_file = self.report_node.save_report(report, filename)
            
            print(f"✅ 报告生成完成，耗时: {time.time() - step4_start:.1f}秒")
            if saved_file:
                print(f"报告已保存至: {saved_file}")
            
            # 总结
            total_duration = time.time() - start_time
            print(f"\n=== ✅ 异步优化工作流执行完成 ===")
            print(f"⏱️ 总耗时: {total_duration:.1f} 秒")
            print(f"📊 候选人数量: {len(evaluations)}")
            print(f"📄 报告文件: {saved_file}")
            
            return {
                "evaluations": evaluations,
                "final_report": report,
                "report_file": saved_file,
                "total_duration": total_duration,
                "parallel_duration": parallel_duration
            }
            
        except Exception as e:
            print(f"\n❌ 异步优化工作流执行失败: {str(e)}")
            raise
    
    async def _handle_requirement_confirmation(self, jd_text: str):
        """处理需求确认（并行任务1）"""
        print("📋 启动需求确认...")
        
        requirement_state = RequirementConfirmationState(jd_text=jd_text)
        
        try:
            # 尝试交互式确认（带超时）
            result = await asyncio.wait_for(
                self._interactive_requirement_confirmation(requirement_state),
                timeout=30  # 30秒超时
            )
            
            if result:
                print("✅ 需求确认完成 (交互模式)")
                return requirement_state.to_job_requirement()
                
        except asyncio.TimeoutError:
            print("⏰ 交互超时，使用自动提取")
        except (EOFError, KeyboardInterrupt):
            print("⚠️ 交互中断，使用自动提取")
        
        # 自动提取需求
        self._auto_extract_requirements(requirement_state)
        print("✅ 需求确认完成 (自动模式)")
        return requirement_state.to_job_requirement()
    
    async def _interactive_requirement_confirmation(self, requirement_state):
        """交互式需求确认"""
        # 生成初始问题
        result = self.requirement_node.process(requirement_state)
        print(f"AI助手: {result['message']}")
        
        max_attempts = 5
        attempt = 0
        
        while not requirement_state.is_complete and attempt < max_attempts:
            try:
                # 在线程池中执行input，避免阻塞
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(None, input, "\nHR: ")
                
                if user_input.lower() in ['quit', 'exit', '退出', '']:
                    break
                    
                result = self.requirement_node.process(requirement_state, user_input)
                print(f"AI助手: {result['message']}")
                
                if result.get('is_complete'):
                    return True
                    
                attempt += 1
                
            except (EOFError, KeyboardInterrupt):
                break
        
        return False
    
    def _auto_extract_requirements(self, requirement_state):
        """自动提取需求"""
        jd_text = requirement_state.jd_text.lower()
        
        # 基于关键词自动提取需求
        must_have = []
        nice_to_have = []
        deal_breaker = []
        
        # 提取必要条件
        if "5年" in jd_text or "5+" in jd_text:
            must_have.append("5年以上工作经验")
        if "java" in jd_text:
            must_have.append("Java开发经验")
        if "spring" in jd_text:
            must_have.append("Spring框架经验")
        if "mysql" in jd_text:
            must_have.append("MySQL数据库经验")
        if "分布式" in jd_text:
            must_have.append("分布式系统经验")
        if "微服务" in jd_text:
            must_have.append("微服务架构经验")
        
        # 提取加分条件
        if "大厂" in jd_text or "bat" in jd_text or "字节" in jd_text:
            nice_to_have.append("大厂工作背景")
        if "开源" in jd_text:
            nice_to_have.append("开源项目贡献")
        if "团队" in jd_text and "管理" in jd_text:
            nice_to_have.append("团队管理经验")
        if "kubernetes" in jd_text or "k8s" in jd_text:
            nice_to_have.append("Kubernetes经验")
        
        # 提取排除条件  
        if "少于" in jd_text or "不足" in jd_text:
            deal_breaker.append("工作经验不足")
        if "无法" in jd_text and "沟通" in jd_text:
            deal_breaker.append("沟通能力差")
            
        # 设置默认值
        if not must_have:
            must_have = ["相关工作经验", "技术基础扎实"]
        if not nice_to_have:
            nice_to_have = ["学习能力强", "团队合作精神"]
        if not deal_breaker:
            deal_breaker = ["经验严重不足"]
        
        # 更新状态
        requirement_state.must_have = must_have
        requirement_state.nice_to_have = nice_to_have
        requirement_state.deal_breaker = deal_breaker
        requirement_state.is_complete = True
        
        print(f"✅ 自动提取需求:")
        print(f"必要条件: {must_have}")
        print(f"加分条件: {nice_to_have}")
        print(f"排除条件: {deal_breaker}")
    
    async def _handle_resume_processing(self, resume_files: List[str]):
        """处理简历解析（并行任务2）"""
        print("📄 启动简历解析...")
        
        # 异步处理简历
        result = await self.resume_node.process(resume_files)
        
        if result["status"] == "success":
            candidate_profiles = result["candidate_profiles"]
            print(f"✅ 简历处理完成，处理了 {len(candidate_profiles)} 个候选人")
            return candidate_profiles
        else:
            raise ValueError(f"简历处理失败: {result['error']}")

    async def _handle_resume_processing_stream(self, resume_files: List[str], progress_callback: Optional[Callable] = None):
        """处理简历文件（带进度）"""
        result = await self.resume_node.process_stream(resume_files, progress_callback)
        
        if result["status"] == "success":
            return result["candidate_profiles"]
        else:
            raise ValueError(f"简历处理失败: {result['error']}")

    async def _handle_dimension_generation_stream(self, job_requirement, progress_callback: Optional[Callable] = None):
        """生成评分维度（带进度）"""
        if progress_callback:
            await progress_callback({
                "stage": "dimension_generation",
                "message": "分析职位要求，生成评分维度",
                "progress": 45,
                "current_item": "评分维度"
            })
        
        result = await asyncio.get_event_loop().run_in_executor(
            None, self.dimension_node.process, job_requirement
        )
        
        if result["status"] != "success":
            raise ValueError(f"评分维度生成失败: {result['error']}")
        
        if progress_callback:
            await progress_callback({
                "stage": "dimension_generation",
                "message": "评分维度生成完成",
                "progress": 50,
                "current_item": "评分维度"
            })
        
        return result["scoring_dimensions"]

    async def _handle_candidate_evaluation_stream(self, candidate_profiles, job_requirement, scoring_dimensions, progress_callback: Optional[Callable] = None):
        """候选人评估（带进度）"""
        result = await self.evaluation_node.process_stream(candidate_profiles, job_requirement, scoring_dimensions, progress_callback)
        
        if result["status"] != "success":
            raise ValueError(f"候选人评分失败: {result['error']}")
        
        return result["evaluations"]

    async def _handle_report_generation_stream(self, evaluation_result, job_requirement, scoring_dimensions, progress_callback: Optional[Callable] = None):
        """报告生成（带进度）"""
        result = await self.report_node.process_stream(evaluation_result, job_requirement, scoring_dimensions, progress_callback)
        
        if result["status"] != "success":
            raise ValueError(f"报告生成失败: {result['error']}")
        
        # 保存报告
        report = result["report"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"candidate_evaluation_report_web_{timestamp}.md"
        saved_file = self.report_node.save_report(report, filename)
        
        return {
            "evaluations": evaluation_result,
            "final_report": report,
            "report_file": saved_file,
            "job_requirement": job_requirement,
            "scoring_dimensions": scoring_dimensions,
            "candidate_count": len(evaluation_result),
            "generated_at": datetime.now().isoformat()
        }


# 性能对比工具
class WorkflowPerformanceComparator:
    """工作流性能对比工具"""
    
    @staticmethod
    async def compare_workflows(jd_text: str, resume_files: List[str]):
        """对比原始工作流和优化工作流的性能"""
        print("🔬 开始工作流性能对比测试")
        print("=" * 60)
        
        # 过滤存在的文件
        existing_files = [f for f in resume_files if os.path.exists(f)]
        if len(existing_files) < 2:
            print("❌ 需要至少2个简历文件来测试")
            return
        
        print(f"📋 使用 {len(existing_files)} 个简历文件进行测试")
        
        # 测试原始工作流
        print(f"\n{'='*20} 测试原始工作流 {'='*20}")
        original_workflow = HRAgentWorkflow()
        original_start = time.time()
        
        try:
            # 使用空输入模拟非交互模式
            await run_with_empty_input(
                original_workflow.run_workflow, jd_text, existing_files[:3]
            )
            original_duration = time.time() - original_start
            print(f"✅ 原始工作流完成，耗时: {original_duration:.1f}秒")
        except Exception as e:
            print(f"❌ 原始工作流失败: {e}")
            original_duration = float('inf')
        
        # 测试优化工作流
        print(f"\n{'='*20} 测试优化工作流 {'='*20}")
        optimized_workflow = OptimizedHRAgentWorkflow(
            max_concurrent_resumes=10,
            max_concurrent_evaluations=8
        )
        optimized_start = time.time()
        
        try:
            result = await run_with_empty_input(
                optimized_workflow.run_optimized_workflow, jd_text, existing_files[:3]
            )
            optimized_duration = time.time() - optimized_start
            print(f"✅ 优化工作流完成，耗时: {optimized_duration:.1f}秒")
            
            # 显示详细性能数据
            if result and "parallel_duration" in result:
                print(f"其中并行处理耗时: {result['parallel_duration']:.1f}秒")
                
        except Exception as e:
            print(f"❌ 优化工作流失败: {e}")
            optimized_duration = float('inf')
        
        # 性能对比
        print(f"\n{'='*20} 性能对比结果 {'='*20}")
        print(f"📊 原始工作流: {original_duration:.1f}秒")
        print(f"🚀 优化工作流: {optimized_duration:.1f}秒")
        
        if original_duration != float('inf') and optimized_duration != float('inf'):
            improvement = ((original_duration - optimized_duration) / original_duration) * 100
            time_saved = original_duration - optimized_duration
            
            print(f"⚡ 性能提升: {improvement:.1f}%")
            print(f"🕒 节省时间: {time_saved:.1f}秒")
            
            if improvement > 0:
                print(f"🎉 优化成功！")
            else:
                print(f"🤔 优化效果不明显")
        else:
            print("❌ 无法进行性能对比")
        
        return {
            "original_duration": original_duration,
            "optimized_duration": optimized_duration,
            "improvement_percentage": improvement if 'improvement' in locals() else 0
        }


async def run_with_empty_input(func, *args):
    """使用空输入运行函数，模拟非交互模式"""
    import sys
    from io import StringIO
    
    # 保存原始stdin
    original_stdin = sys.stdin
    
    try:
        # 使用空输入
        sys.stdin = StringIO("\n" * 10)
        result = await func(*args)
        return result
    finally:
        # 恢复原始stdin
        sys.stdin = original_stdin


# 使用示例
async def main():
    """简化优化工作流使用示例"""
    jd_text = """
高级后端开发工程师

岗位职责：
- 负责核心交易系统的架构设计和开发
- 设计高并发、高可用的微服务系统
- 优化系统性能，处理大规模数据

任职要求：
- 5年以上后端开发经验
- 熟练掌握Java、Spring Boot等技术
- 有分布式系统设计经验
- 了解Docker、Kubernetes
"""
    
    resume_files = [
        "examples/resume_candidate_a.txt",
        "examples/resume_candidate_b.txt", 
        "examples/resume_candidate_c.txt"
    ]
    
    # 运行优化工作流
    optimized_workflow = OptimizedHRAgentWorkflow(
        max_concurrent_resumes=10,
        max_concurrent_evaluations=8
    )
    
    try:
        result = await optimized_workflow.run_optimized_workflow(jd_text, resume_files)
        print(f"\n🎉 异步优化工作流执行成功!")
        
        # 可选：性能对比
        print(f"\n{'='*60}")
        await WorkflowPerformanceComparator.compare_workflows(jd_text, resume_files)
        
    except Exception as e:
        print(f"❌ 异步优化工作流执行失败: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())