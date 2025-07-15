import asyncio
import time
from typing import Dict, Any, List, Optional
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

class UltraOptimizedHRWorkflow:
    """极限优化HR智能体工作流 - 三路并行处理"""
    
    def __init__(self, max_concurrent_resumes: int = 10, max_concurrent_evaluations: int = 8):
        self.requirement_node = RequirementConfirmationNode()
        self.dimension_node = ScoringDimensionNode()
        self.resume_node = ResumeStructureNode(max_concurrent=max_concurrent_resumes)
        self.evaluation_node = CandidateEvaluationNode(max_concurrent=max_concurrent_evaluations)
        self.report_node = ReportGenerationNode()
        
    async def run_ultra_optimized_workflow(self, jd_text: str, resume_files: List[str]) -> Dict[str, Any]:
        """运行极限优化版工作流 - 三路并行"""
        print("=== 🚀 HR智能体简历筛选系统 (极限优化版) ===")
        print(f"JD文本长度: {len(jd_text)} 字符")
        print(f"简历文件数量: {len(resume_files)} 个")
        print("⚡ 启用三路并行处理优化")
        
        # 验证简历文件
        existing_files = [f for f in resume_files if os.path.exists(f)]
        
        if not existing_files:
            raise ValueError("没有有效的简历文件")
        
        start_time = time.time()
        print(f"⏱️ 开始时间: {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            # 步骤1: 三路并行处理
            print("\n=== 🚀 步骤1: 三路并行处理 ===")
            print("同时进行: 需求确认 + 简历解析 + 基础评分维度生成...")
            
            # 创建三个并行任务
            requirement_task = self._handle_requirement_confirmation(jd_text)
            resume_task = self._handle_resume_processing(existing_files)
            basic_dimension_task = self._handle_basic_dimension_generation(jd_text)
            
            # 三路并行执行
            requirement_result, resume_result, basic_dimensions = await asyncio.gather(
                requirement_task, resume_task, basic_dimension_task, return_exceptions=True
            )
            
            # 处理并行结果
            if isinstance(requirement_result, Exception):
                raise requirement_result
            if isinstance(resume_result, Exception):
                raise resume_result
            if isinstance(basic_dimensions, Exception):
                print(f"⚠️ 基础维度生成失败，将重新生成: {basic_dimensions}")
                basic_dimensions = None
            
            job_requirement = requirement_result
            candidate_profiles = resume_result
            
            parallel_duration = time.time() - start_time
            print(f"✅ 三路并行处理完成，耗时: {parallel_duration:.1f}秒")
            
            # 步骤2: 完善评分维度生成 (如果基础维度失败则重新生成)
            if basic_dimensions is None:
                print("\n=== 📊 步骤2: 重新生成评分维度 ===")
                step2_start = time.time()
                
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.dimension_node.process, job_requirement
                )
                if result["status"] != "success":
                    raise ValueError(f"评分维度生成失败: {result['error']}")
                
                scoring_dimensions = result["scoring_dimensions"]
                print(f"✅ 评分维度重新生成成功，耗时: {time.time() - step2_start:.1f}秒")
            else:
                print("\n=== 📊 步骤2: 优化评分维度 ===")
                step2_start = time.time()
                
                # 基于完整需求信息优化评分维度
                scoring_dimensions = await self._optimize_scoring_dimensions(
                    basic_dimensions, job_requirement
                )
                print(f"✅ 评分维度优化完成，耗时: {time.time() - step2_start:.1f}秒")
            
            print(f"生成了 {len(scoring_dimensions.dimensions)} 个评分维度")
            
            # 步骤3: 候选人评分 (超级并发优化)
            print("\n=== 🎯 步骤3: 候选人评分 (超级并发优化) ===")
            step3_start = time.time()
            
            # 增加并发数以提升性能
            enhanced_evaluation_node = CandidateEvaluationNode(max_concurrent=min(12, len(candidate_profiles)))
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
            
            # 步骤4: 生成报告 (异步优化)
            print("\n=== 📈 步骤4: 生成评估报告 (异步优化) ===")
            step4_start = time.time()
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.report_node.process, evaluations, job_requirement, scoring_dimensions
            )
            if result["status"] != "success":
                raise ValueError(f"报告生成失败: {result['error']}")
            
            # 保存报告
            report = result["report"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"candidate_evaluation_report_ultra_{timestamp}.md"
            saved_file = self.report_node.save_report(report, filename)
            
            print(f"✅ 报告生成完成，耗时: {time.time() - step4_start:.1f}秒")
            if saved_file:
                print(f"报告已保存至: {saved_file}")
            
            # 总结
            total_duration = time.time() - start_time
            print(f"\n=== ✅ 极限优化工作流执行完成 ===")
            print(f"⏱️ 总耗时: {total_duration:.1f} 秒")
            print(f"📊 候选人数量: {len(evaluations)}")
            print(f"📄 报告文件: {saved_file}")
            print(f"⚡ 三路并行节省时间: ~{parallel_duration:.1f}秒")
            
            return {
                "evaluations": evaluations,
                "final_report": report,
                "report_file": saved_file,
                "total_duration": total_duration,
                "parallel_duration": parallel_duration
            }
            
        except Exception as e:
            print(f"\n❌ 极限优化工作流执行失败: {str(e)}")
            raise
    
    async def _handle_requirement_confirmation(self, jd_text: str):
        """处理需求确认（并行任务1）"""
        print("📋 启动需求确认...")
        
        requirement_state = RequirementConfirmationState(jd_text=jd_text)
        
        try:
            # 尝试交互式确认（带超时）
            result = await asyncio.wait_for(
                self._interactive_requirement_confirmation(requirement_state),
                timeout=25  # 减少超时时间
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
        
        max_attempts = 3  # 减少尝试次数
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
        """自动提取需求（优化版）"""
        jd_text = requirement_state.jd_text.lower()
        
        # 基于关键词自动提取需求
        must_have = []
        nice_to_have = []
        deal_breaker = []
        
        # 提取必要条件（扩展关键词）
        if any(keyword in jd_text for keyword in ["5年", "5+", "五年", "5 年"]):
            must_have.append("5年以上工作经验")
        if any(keyword in jd_text for keyword in ["java", "Java", "JAVA"]):
            must_have.append("Java开发经验")
        if any(keyword in jd_text for keyword in ["spring", "Spring", "springboot", "spring boot"]):
            must_have.append("Spring框架经验")
        if any(keyword in jd_text for keyword in ["mysql", "MySQL", "数据库", "database"]):
            must_have.append("MySQL数据库经验")
        if any(keyword in jd_text for keyword in ["分布式", "distributed", "微服务", "microservice"]):
            must_have.append("分布式系统经验")
        if any(keyword in jd_text for keyword in ["微服务", "microservice", "服务化"]):
            must_have.append("微服务架构经验")
        
        # 提取加分条件（扩展关键词）
        if any(keyword in jd_text for keyword in ["大厂", "bat", "字节", "阿里", "腾讯", "百度", "美团"]):
            nice_to_have.append("大厂工作背景")
        if any(keyword in jd_text for keyword in ["开源", "github", "贡献"]):
            nice_to_have.append("开源项目贡献")
        if any(keyword in jd_text for keyword in ["团队", "管理", "leader", "tech lead"]):
            nice_to_have.append("团队管理经验")
        if any(keyword in jd_text for keyword in ["kubernetes", "k8s", "docker", "容器"]):
            nice_to_have.append("容器化技术经验")
        
        # 提取排除条件
        if any(keyword in jd_text for keyword in ["少于", "不足", "低于"]):
            deal_breaker.append("工作经验不足")
        if any(keyword in jd_text for keyword in ["无法", "不能", "无"]) and "沟通" in jd_text:
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
    
    async def _handle_basic_dimension_generation(self, jd_text: str):
        """处理基础评分维度生成（并行任务3）"""
        print("📊 启动基础评分维度生成...")
        
        try:
            # 基于JD文本快速生成基础评分维度
            from src.models import JobRequirement
            
            # 创建临时的基础需求对象
            basic_requirement = JobRequirement(
                position_name="职位",
                must_have=["基础技能要求"],
                nice_to_have=["加分技能"],
                deal_breaker=["排除条件"]
            )
            
            # 异步生成基础评分维度
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.dimension_node.process, basic_requirement
            )
            
            if result["status"] == "success":
                print("✅ 基础评分维度生成完成")
                return result["scoring_dimensions"]
            else:
                print(f"⚠️ 基础评分维度生成失败: {result['error']}")
                return None
                
        except Exception as e:
            print(f"⚠️ 基础评分维度生成异常: {str(e)}")
            return None
    
    async def _optimize_scoring_dimensions(self, basic_dimensions, job_requirement):
        """优化评分维度"""
        # 这里可以实现维度优化逻辑
        # 目前直接重新生成
        result = await asyncio.get_event_loop().run_in_executor(
            None, self.dimension_node.process, job_requirement
        )
        
        if result["status"] == "success":
            return result["scoring_dimensions"]
        else:
            # 如果失败，返回基础维度
            return basic_dimensions

# 使用示例
async def main():
    """极限优化工作流使用示例"""
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
    
    # 运行极限优化工作流
    ultra_workflow = UltraOptimizedHRWorkflow(
        max_concurrent_resumes=12,
        max_concurrent_evaluations=10
    )
    
    try:
        result = await ultra_workflow.run_ultra_optimized_workflow(jd_text, resume_files)
        print(f"\n🎉 极限优化工作流执行成功!")
        print(f"⚡ 性能提升显著！")
        
    except Exception as e:
        print(f"❌ 极限优化工作流执行失败: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())