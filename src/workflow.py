import asyncio
from typing import Dict, Any, List, Optional, Callable
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END, START
from langgraph.graph.state import CompiledStateGraph
from src.models import (
    WorkflowState, 
    RequirementConfirmationState,
    JobRequirement,
    ScoringDimensions,
    CandidateProfile,
    CandidateEvaluation
)
from src.nodes import (
    RequirementConfirmationNode,
    ScoringDimensionNode,
    ResumeStructureNode,
    CandidateEvaluationNode,
    ReportGenerationNode
)
import os
from datetime import datetime

class HRWorkflowState(TypedDict):
    """HR工作流状态类"""
    jd_text: Optional[str]
    resume_files: List[str]
    job_requirement: Optional[JobRequirement]
    scoring_dimensions: Optional[ScoringDimensions]
    candidate_profiles: List[CandidateProfile]
    evaluations: List[CandidateEvaluation]
    final_report: Optional[str]
    report_file: Optional[str]
    current_step: str
    session_id: str
    created_at: str
    error_message: Optional[str]

class HRAgentWorkflow:
    """HR智能体工作流 - 基于LangGraph的完整招聘流程"""
    
    def __init__(self):
        self.requirement_node = RequirementConfirmationNode()
        self.dimension_node = ScoringDimensionNode()
        self.resume_node = ResumeStructureNode()
        self.evaluation_node = CandidateEvaluationNode()
        self.report_node = ReportGenerationNode()
        
        # 状态管理
        self.workflow_state = WorkflowState()
        self.requirement_state = None
        
        # 构建工作流图
        self.graph = self._build_workflow_graph()
        
    def _build_workflow_graph(self) -> CompiledStateGraph:
        """构建工作流图"""
        # 创建状态图
        workflow = StateGraph(HRWorkflowState)
        
        # 添加节点
        workflow.add_node("requirement_confirmation", self._requirement_confirmation_step)
        workflow.add_node("dimension_generation", self._dimension_generation_step)
        workflow.add_node("resume_processing", self._resume_processing_step)
        workflow.add_node("candidate_evaluation", self._candidate_evaluation_step)
        workflow.add_node("report_generation", self._report_generation_step)
        
        # 添加边
        workflow.add_edge(START, "requirement_confirmation")
        workflow.add_edge("requirement_confirmation", "dimension_generation")
        workflow.add_edge("dimension_generation", "resume_processing")
        workflow.add_edge("resume_processing", "candidate_evaluation")
        workflow.add_edge("candidate_evaluation", "report_generation")
        workflow.add_edge("report_generation", END)
        
        # 编译图
        return workflow.compile()
    
    async def _requirement_confirmation_step(self, state: HRWorkflowState) -> HRWorkflowState:
        """需求确认步骤"""
        print("\n=== 步骤1: 需求确认 ===")
        
        jd_text = state["jd_text"]
        if not jd_text:
            raise ValueError("缺少JD文本")
        
        # 初始化需求确认状态
        self.requirement_state = RequirementConfirmationState(jd_text=jd_text)
        
        # 开始交互确认
        print("开始与HR确认招聘需求...")
        
        # 生成初始问题
        result = self.requirement_node.process(self.requirement_state)
        print(f"AI助手: {result['message']}")
        
        # 交互循环
        max_attempts = 10  # 最大交互次数
        attempt = 0
        
        while not self.requirement_state.is_complete and attempt < max_attempts:
            try:
                user_input = input("\nHR: ")
                if user_input.lower() in ['quit', 'exit', '退出']:
                    break
                    
                result = self.requirement_node.process(self.requirement_state, user_input)
                print(f"AI助手: {result['message']}")
                
                if result.get('is_complete'):
                    print("✓ 需求确认完成")
                    break
                    
                attempt += 1
                
            except (EOFError, KeyboardInterrupt):
                print("\n⚠️ 交互中断，使用基于JD的默认需求确认")
                # 使用JD自动提取需求
                self._auto_extract_requirements_from_jd()
                break
        
        # 更新状态
        job_requirement = self.requirement_state.to_job_requirement()
        self.workflow_state.job_requirement = job_requirement
        self.workflow_state.current_step = "requirement_confirmation"
        
        # 更新并返回状态
        state["job_requirement"] = job_requirement
        state["current_step"] = "requirement_confirmation"
        return state
    
    def _auto_extract_requirements_from_jd(self):
        """从JD自动提取需求"""
        jd_text = self.requirement_state.jd_text.lower()
        
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
        self.requirement_state.must_have = must_have
        self.requirement_state.nice_to_have = nice_to_have
        self.requirement_state.deal_breaker = deal_breaker
        self.requirement_state.is_complete = True
        
        print(f"✅ 自动提取需求完成:")
        print(f"必要条件: {must_have}")
        print(f"加分条件: {nice_to_have}")
        print(f"排除条件: {deal_breaker}")
    
    async def _dimension_generation_step(self, state: HRWorkflowState) -> HRWorkflowState:
        """评分维度生成步骤"""
        print("\n=== 步骤2: 生成评分维度 ===")
        
        job_requirement = state["job_requirement"]
        if not job_requirement:
            raise ValueError("缺少招聘需求")
        
        # 生成评分维度
        result = self.dimension_node.process(job_requirement)
        
        if result["status"] == "success":
            scoring_dimensions = result["scoring_dimensions"]
            print("✓ 评分维度生成成功")
            print(f"生成了 {len(scoring_dimensions.dimensions)} 个评分维度")
            
            for dim in scoring_dimensions.dimensions:
                print(f"- {dim.name} (权重: {dim.weight:.1%})")
            
            # 更新状态
            self.workflow_state.scoring_dimensions = scoring_dimensions
            self.workflow_state.current_step = "dimension_generation"
            
            # 更新并返回状态
            state["scoring_dimensions"] = scoring_dimensions
            state["current_step"] = "dimension_generation"
            return state
        else:
            raise ValueError(f"评分维度生成失败: {result['error']}")
    
    async def _resume_processing_step(self, state: HRWorkflowState) -> HRWorkflowState:
        """简历处理步骤"""
        print("\n=== 步骤3: 简历结构化处理 ===")
        
        resume_files = state["resume_files"]
        if not resume_files:
            raise ValueError("缺少简历文件")
        
        # 处理简历
        result = await self.resume_node.process(resume_files)
        
        if result["status"] == "success":
            candidate_profiles = result["candidate_profiles"]
            print(f"✓ 简历处理完成")
            print(f"成功处理 {len(candidate_profiles)} 个候选人")
            
            # 更新状态
            self.workflow_state.candidate_profiles = candidate_profiles
            self.workflow_state.current_step = "resume_processing"
            
            # 更新并返回状态
            state["candidate_profiles"] = candidate_profiles
            state["current_step"] = "resume_processing"
            return state
        else:
            raise ValueError(f"简历处理失败: {result['error']}")
    
    async def _candidate_evaluation_step(self, state: HRWorkflowState) -> HRWorkflowState:
        """候选人评分步骤"""
        print("\n=== 步骤4: 候选人评分 ===")
        
        candidate_profiles = state["candidate_profiles"]
        job_requirement = state["job_requirement"]
        scoring_dimensions = state["scoring_dimensions"]
        
        if not candidate_profiles:
            raise ValueError("缺少候选人档案")
        if not job_requirement:
            raise ValueError("缺少招聘需求")
        if not scoring_dimensions:
            raise ValueError("缺少评分维度")
        
        # 评分候选人
        result = await self.evaluation_node.process(
            candidate_profiles, job_requirement, scoring_dimensions
        )
        
        if result["status"] == "success":
            evaluations = result["evaluations"]
            print(f"✓ 候选人评分完成")
            print(f"成功评分 {len(evaluations)} 个候选人")
            
            # 显示排名
            print("\n候选人排名:")
            for eval in evaluations[:5]:  # 显示前5名
                print(f"{eval.ranking}. {eval.candidate_name} - {eval.overall_score:.1f}/10")
            
            # 更新状态
            self.workflow_state.evaluations = evaluations
            self.workflow_state.current_step = "candidate_evaluation"
            
            # 更新并返回状态
            state["evaluations"] = evaluations
            state["current_step"] = "candidate_evaluation"
            return state
        else:
            raise ValueError(f"候选人评分失败: {result['error']}")
    
    async def _report_generation_step(self, state: HRWorkflowState) -> HRWorkflowState:
        """报告生成步骤"""
        print("\n=== 步骤5: 生成评估报告 ===")
        
        evaluations = state["evaluations"]
        job_requirement = state["job_requirement"]
        scoring_dimensions = state["scoring_dimensions"]
        
        if not evaluations:
            raise ValueError("缺少评价结果")
        if not job_requirement:
            raise ValueError("缺少招聘需求")
        if not scoring_dimensions:
            raise ValueError("缺少评分维度")
        
        # 生成报告
        result = self.report_node.process(evaluations, job_requirement, scoring_dimensions)
        
        if result["status"] == "success":
            report = result["report"]
            print("✓ 报告生成成功")
            
            # 保存报告
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"candidate_evaluation_report_{timestamp}.md"
            saved_file = self.report_node.save_report(report, filename)
            
            if saved_file:
                print(f"报告已保存至: {saved_file}")
            
            # 更新状态
            self.workflow_state.final_report = report
            self.workflow_state.current_step = "report_generation"
            
            # 更新并返回状态
            state["final_report"] = report
            state["report_file"] = saved_file
            state["current_step"] = "report_generation"
            return state
        else:
            raise ValueError(f"报告生成失败: {result['error']}")
    
    async def run_workflow(self, jd_text: str, resume_files: List[str]) -> Dict[str, Any]:
        """运行完整工作流"""
        print("=== HR智能体简历筛选系统 ===")
        print(f"JD文本长度: {len(jd_text)} 字符")
        print(f"简历文件数量: {len(resume_files)} 个")
        
        # 验证简历文件
        existing_files = []
        for file_path in resume_files:
            if os.path.exists(file_path):
                existing_files.append(file_path)
            else:
                print(f"⚠️ 文件不存在: {file_path}")
        
        if not existing_files:
            raise ValueError("没有有效的简历文件")
        
        # 准备初始状态
        initial_state: HRWorkflowState = {
            "jd_text": jd_text,
            "resume_files": existing_files,
            "job_requirement": None,
            "scoring_dimensions": None,
            "candidate_profiles": [],
            "evaluations": [],
            "final_report": None,
            "report_file": None,
            "current_step": "start",
            "session_id": self.workflow_state.session_id,
            "created_at": datetime.now().isoformat(),
            "error_message": None
        }
        
        try:
            # 运行工作流
            result = await self.graph.ainvoke(initial_state)
            
            print("\n=== 工作流执行完成 ===")
            print(f"候选人数量: {len(result['evaluations'])}")
            print(f"报告文件: {result.get('report_file', '未保存')}")
            
            return dict(result)
            
        except Exception as e:
            print(f"\n❌ 工作流执行失败: {str(e)}")
            self.workflow_state.error_message = str(e)
            raise
    
    def get_workflow_state(self) -> WorkflowState:
        """获取工作流状态"""
        return self.workflow_state
    
    def reset_workflow(self):
        """重置工作流状态"""
        self.workflow_state = WorkflowState()
        self.requirement_state = None


# 使用示例
async def main():
    # 示例JD
    jd_text = """
    高级后端开发工程师
    
    岗位职责：
    - 负责核心交易系统的架构设计和开发
    - 设计高并发、高可用的微服务系统
    - 优化系统性能，处理大规模数据
    
    任职要求：
    - 5年以上后端开发经验
    - 熟练掌握Node.js、Python等语言
    - 有分布式系统设计经验
    - 了解Docker、Kubernetes
    """
    
    # 示例简历文件
    resume_files = [
        "examples/resume1.pdf",
        "examples/resume2.docx",
        "examples/resume3.txt"
    ]
    
    # 创建工作流
    workflow = HRAgentWorkflow()
    
    try:
        # 运行工作流
        result = await workflow.run_workflow(jd_text, resume_files)
        print(f"\n✅ 工作流执行成功!")
        print(f"最终报告: {result.get('final_report', '无')[:200]}...")
        
    except Exception as e:
        print(f"❌ 工作流执行失败: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())