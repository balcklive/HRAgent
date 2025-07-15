# Author: Peng Fei

import asyncio
from typing import List, Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from src.models import (
    CandidateProfile,
    JobRequirement,
    ScoringDimensions,
    CandidateEvaluation,
    DimensionScore,
    EvaluationStatus
)
from src.prompts import (
    CANDIDATE_EVALUATION_SYSTEM_PROMPT,
    CANDIDATE_EVALUATION_PROMPT_TEMPLATE
)
import json
import re
from concurrent.futures import ThreadPoolExecutor

class CandidateEvaluationNode:
    """候选人评分节点 - 基于评分维度对候选人进行评分"""
    
    def __init__(self, 
                 model_name: str = "gpt-4o-mini", 
                 temperature: float = 0.3,
                 max_concurrent: int = 3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.max_concurrent = max_concurrent
        self.system_prompt = CANDIDATE_EVALUATION_SYSTEM_PROMPT
        
    async def process(self, 
                     candidates: List[CandidateProfile],
                     job_requirement: JobRequirement,
                     scoring_dimensions: ScoringDimensions) -> Dict[str, Any]:
        """处理候选人评分"""
        try:
            print(f"开始评分 {len(candidates)} 个候选人...")
            
            # 并发评分
            evaluations = await self._evaluate_candidates_concurrently(
                candidates, job_requirement, scoring_dimensions
            )
            
            # 排序
            evaluations = sorted(evaluations, key=lambda x: x.overall_score, reverse=True)
            
            # 设置排名
            for i, evaluation in enumerate(evaluations, 1):
                evaluation.ranking = i
            
            success_count = len([e for e in evaluations if e.overall_score > 0])
            
            return {
                "status": "success",
                "total_candidates": len(candidates),
                "successful_evaluations": success_count,
                "evaluations": evaluations
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "evaluations": []
            }

    async def process_stream(self, candidates: List[CandidateProfile], 
                            job_requirement: JobRequirement, 
                            scoring_dimensions: ScoringDimensions,
                            progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """评估候选人（带进度流式输出）"""
        try:
            if progress_callback:
                await progress_callback({
                    "stage": "candidate_evaluation",
                    "message": "开始候选人评估",
                    "progress": 60,
                    "total_items": len(candidates),
                    "completed_items": 0
                })
            
            # 所有传入的候选人都应该是有效的CandidateProfile对象
            valid_candidates = candidates
            
            if progress_callback:
                await progress_callback({
                    "stage": "candidate_evaluation",
                    "message": f"找到 {len(valid_candidates)} 个有效候选人",
                    "progress": 65,
                    "total_items": len(valid_candidates),
                    "completed_items": 0
                })
            
            # 并发评估
            evaluations = await self._evaluate_candidates_concurrently_stream(
                valid_candidates, job_requirement, scoring_dimensions, progress_callback
            )
            
            # 排序
            evaluations = sorted(evaluations, key=lambda x: x.overall_score, reverse=True)
            
            # 设置排名
            for i, evaluation in enumerate(evaluations, 1):
                evaluation.ranking = i
            
            # 生成结果
            if progress_callback:
                await progress_callback({
                    "stage": "candidate_evaluation",
                    "message": "生成评估结果",
                    "progress": 85,
                    "total_items": len(evaluations),
                    "completed_items": len(evaluations)
                })
            
            success_count = len([e for e in evaluations if e.overall_score > 0])
            
            if progress_callback:
                await progress_callback({
                    "stage": "candidate_evaluation",
                    "message": "候选人评估完成",
                    "progress": 90,
                    "total_items": len(candidates),
                    "completed_items": len(candidates)
                })
            
            return {
                "status": "success",
                "total_candidates": len(candidates),
                "successful_evaluations": success_count,
                "evaluations": evaluations
            }
            
        except Exception as e:
            if progress_callback:
                await progress_callback({
                    "stage": "candidate_evaluation",
                    "message": f"评估失败: {str(e)}",
                    "progress": 60,
                    "error": str(e)
                })
            
            return {
                "status": "error",
                "error": str(e),
                "evaluations": []
            }
    
    async def _evaluate_candidates_concurrently(self, 
                                              candidates: List[CandidateProfile],
                                              job_requirement: JobRequirement,
                                              scoring_dimensions: ScoringDimensions) -> List[CandidateEvaluation]:
        """并发评分候选人"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def evaluate_single_candidate(candidate):
            async with semaphore:
                return await self._evaluate_single_candidate(candidate, job_requirement, scoring_dimensions)
        
        tasks = [evaluate_single_candidate(candidate) for candidate in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        evaluations = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 创建错误评价
                error_evaluation = CandidateEvaluation(
                    candidate_id=candidates[i].id,
                    candidate_name=candidates[i].basic_info.name,
                    dimension_scores=[],
                    overall_score=0.0,
                    recommendation=f"评分失败: {str(result)}",
                    strengths=[],
                    weaknesses=["评分过程中出现错误"]
                )
                evaluations.append(error_evaluation)
            else:
                evaluations.append(result)
        
        return evaluations
    
    async def _evaluate_single_candidate(self, 
                                       candidate: CandidateProfile,
                                       job_requirement: JobRequirement,
                                       scoring_dimensions: ScoringDimensions) -> CandidateEvaluation:
        """评分单个候选人"""
        try:
            # 构建评分提示
            prompt = self._build_evaluation_prompt(candidate, job_requirement, scoring_dimensions)
            
            # 调用LLM
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # 解析响应
            evaluation_data = self._parse_evaluation_response(response.content)
            
            # 创建评分对象
            evaluation = self._create_candidate_evaluation(
                candidate, evaluation_data, scoring_dimensions
            )
            
            return evaluation
            
        except Exception as e:
            # 返回错误评价
            return CandidateEvaluation(
                candidate_id=candidate.id,
                candidate_name=candidate.basic_info.name,
                dimension_scores=[],
                overall_score=0.0,
                recommendation=f"评分失败: {str(e)}",
                strengths=[],
                weaknesses=["评分过程中出现错误"]
            )
    
    def _build_evaluation_prompt(self, 
                               candidate: CandidateProfile,
                               job_requirement: JobRequirement,
                               scoring_dimensions: ScoringDimensions) -> str:
        """构建评分提示"""
        candidate_info = self._format_candidate_info(candidate)
        requirements_info = self._format_requirements_info(job_requirement)
        dimensions_info = self._format_dimensions_info(scoring_dimensions)
        
        return CANDIDATE_EVALUATION_PROMPT_TEMPLATE.format(
            candidate_info=candidate_info,
            requirements_info=requirements_info,
            dimensions_info=dimensions_info
        )
    
    def _format_candidate_info(self, candidate: CandidateProfile) -> str:
        """格式化候选人信息"""
        basic_info = candidate.basic_info
        education_info = candidate.education[0] if candidate.education else None
        
        info_parts = []
        
        # 基本信息
        info_parts.append(f"姓名: {basic_info.name}")
        info_parts.append(f"当前职位: {basic_info.current_role}")
        info_parts.append(f"当前公司: {basic_info.current_company}")
        info_parts.append(f"工作经验: {basic_info.experience_years}年")
        info_parts.append(f"所在地: {basic_info.location}")
        
        # 教育背景
        if education_info:
            info_parts.append(f"教育背景: {education_info.degree} {education_info.major}, {education_info.school}")
        
        # 工作经历
        if candidate.work_experience:
            info_parts.append("\n工作经历:")
            for exp in candidate.work_experience[:3]:  # 只显示最近3段经历
                info_parts.append(f"- {exp.company} ({exp.start_date} - {exp.end_date})")
                info_parts.append(f"  职位: {exp.position}")
                if exp.description:
                    info_parts.append(f"  描述: {exp.description[:100]}...")
        
        # 技能信息
        if candidate.skills:
            info_parts.append("\n技能:")
            for skill in candidate.skills[:5]:  # 只显示前5个技能
                info_parts.append(f"- {skill.name} ({skill.level}, {skill.years_experience}年)")
        
        return "\n".join(info_parts)
    
    def _format_requirements_info(self, job_requirement: JobRequirement) -> str:
        """格式化招聘需求信息"""
        parts = []
        parts.append(f"职位: {job_requirement.position}")
        
        if job_requirement.must_have:
            parts.append("必要条件:")
            for req in job_requirement.must_have:
                parts.append(f"- {req}")
        
        if job_requirement.nice_to_have:
            parts.append("加分条件:")
            for req in job_requirement.nice_to_have:
                parts.append(f"- {req}")
        
        if job_requirement.deal_breaker:
            parts.append("排除条件:")
            for req in job_requirement.deal_breaker:
                parts.append(f"- {req}")
        
        return "\n".join(parts)
    
    def _format_dimensions_info(self, scoring_dimensions: ScoringDimensions) -> str:
        """格式化评分维度信息"""
        parts = []
        for dimension in scoring_dimensions.dimensions:
            parts.append(f"维度: {dimension.name} (权重: {dimension.weight:.0%})")
            parts.append(f"字段: {', '.join(dimension.fields)}")
            parts.append(f"描述: {dimension.description}")
            parts.append("")
        
        return "\n".join(parts)
    
    def _parse_evaluation_response(self, response: str) -> Dict[str, Any]:
        """解析评估响应"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # 如果没有```json```标记，尝试直接解析
            lines = response.split('\n')
            json_start = -1
            json_end = -1
            
            for i, line in enumerate(lines):
                if '{' in line and json_start == -1:
                    json_start = i
                if '}' in line and json_start != -1:
                    json_end = i
                    break
            
            if json_start != -1 and json_end != -1:
                json_str = '\n'.join(lines[json_start:json_end+1])
                return json.loads(json_str)
            
            # 如果都失败，返回默认评估
            return self._get_default_evaluation()
            
        except json.JSONDecodeError:
            return self._get_default_evaluation()
    
    def _get_default_evaluation(self) -> Dict[str, Any]:
        """获取默认评估结果"""
        return {
            "dimension_scores": [],
            "overall_score": 0.0,
            "recommendation": "无法解析评估结果",
            "strengths": [],
            "weaknesses": ["评估过程中出现错误"]
        }
    
    def _create_candidate_evaluation(self, 
                                   candidate: CandidateProfile,
                                   evaluation_data: Dict[str, Any],
                                   scoring_dimensions: ScoringDimensions) -> CandidateEvaluation:
        """创建候选人评估对象"""
        # 解析维度评分
        dimension_scores = []
        for dim_score_data in evaluation_data.get("dimension_scores", []):
            try:
                dimension_score = DimensionScore(
                    dimension_name=dim_score_data["dimension_name"],
                    score=float(dim_score_data["score"]),
                    status=EvaluationStatus(dim_score_data["status"]),
                    details=dim_score_data.get("details", {}),
                    comments=dim_score_data.get("comments", "")
                )
                dimension_scores.append(dimension_score)
            except Exception as e:
                print(f"解析维度评分失败: {str(e)}")
                continue
        
        # 计算总体评分
        overall_score = evaluation_data.get("overall_score", 0.0)
        if not overall_score and dimension_scores:
            # 如果没有总体评分，根据维度评分计算
            total_weighted_score = 0.0
            total_weight = 0.0
            
            for dim_score in dimension_scores:
                # 找到对应的维度权重
                for dimension in scoring_dimensions.dimensions:
                    if dimension.name == dim_score.dimension_name:
                        total_weighted_score += dim_score.score * dimension.weight
                        total_weight += dimension.weight
                        break
            
            if total_weight > 0:
                overall_score = total_weighted_score / total_weight
        
        return CandidateEvaluation(
            candidate_id=candidate.id,
            candidate_name=candidate.basic_info.name,
            dimension_scores=dimension_scores,
            overall_score=overall_score,
            recommendation=evaluation_data.get("recommendation", ""),
            strengths=evaluation_data.get("strengths", []),
            weaknesses=evaluation_data.get("weaknesses", [])
        )

    async def _evaluate_candidates_concurrently_stream(self, 
                                                      candidates: List[CandidateProfile],
                                                      job_requirement: JobRequirement,
                                                      scoring_dimensions: ScoringDimensions,
                                                      progress_callback: Optional[Callable] = None) -> List[CandidateEvaluation]:
        """并发评分候选人（带进度）"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        completed_count = 0
        
        async def evaluate_single_candidate_stream(candidate):
            nonlocal completed_count
            async with semaphore:
                if progress_callback:
                    await progress_callback({
                        "stage": "candidate_evaluation",
                        "message": f"评估候选人: {candidate.basic_info.name}",
                        "progress": 65 + (completed_count / len(candidates)) * 15,
                        "current_item": candidate.basic_info.name,
                        "total_items": len(candidates),
                        "completed_items": completed_count
                    })
                
                result = await self._evaluate_single_candidate(candidate, job_requirement, scoring_dimensions)
                completed_count += 1
                
                if progress_callback:
                    await progress_callback({
                        "stage": "candidate_evaluation",
                        "message": f"完成评估: {candidate.basic_info.name} (得分: {result.overall_score:.1f})",
                        "progress": 65 + (completed_count / len(candidates)) * 15,
                        "current_item": candidate.basic_info.name,
                        "total_items": len(candidates),
                        "completed_items": completed_count
                    })
                
                return result
        
        tasks = [evaluate_single_candidate_stream(candidate) for candidate in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        evaluations = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 创建错误评价
                error_evaluation = CandidateEvaluation(
                    candidate_id=candidates[i].id,
                    candidate_name=candidates[i].basic_info.name,
                    dimension_scores=[],
                    overall_score=0.0,
                    recommendation=f"评分失败: {str(result)}",
                    strengths=[],
                    weaknesses=["评分过程中出现错误"]
                )
                evaluations.append(error_evaluation)
            else:
                evaluations.append(result)
        
        return evaluations
    
    async def run_standalone(self, 
                           candidates: List[CandidateProfile],
                           job_requirement: JobRequirement,
                           scoring_dimensions: ScoringDimensions) -> List[CandidateEvaluation]:
        """独立运行模式"""
        result = await self.process(candidates, job_requirement, scoring_dimensions)
        
        if result["status"] == "success":
            print(f"评分完成: {result['successful_evaluations']}/{result['total_candidates']} 个候选人")
            return result["evaluations"]
        else:
            print(f"评分失败: {result['error']}")
            return []

async def main():
    """测试函数"""
    from src.models import CandidateProfile, CandidateBasicInfo, JobRequirement, ScoringDimensions, ScoringDimension
    
    # 创建测试数据
    candidates = [
        CandidateProfile(
            id="1",
            basic_info=CandidateBasicInfo(
                name="张三",
                email="zhangsan@example.com",
                phone="13800138000",
                location="北京",
                experience_years=5,
                current_role="高级软件工程师",
                current_company="腾讯"
            ),
            education=[],
            work_experience=[],
            skills=[]
        )
    ]
    
    job_requirement = JobRequirement(
        position="Python开发工程师",
        must_have=["Python", "Django", "3年以上经验"],
        nice_to_have=["Redis", "Docker"],
        deal_breaker=["无编程经验"]
    )
    
    scoring_dimensions = ScoringDimensions(
        dimensions=[
            ScoringDimension(
                name="技能匹配",
                weight=0.6,
                fields=["Python", "Django", "数据库"],
                description="技术技能匹配度"
            ),
            ScoringDimension(
                name="经验评估", 
                weight=0.4,
                fields=["工作经验", "项目经验"],
                description="工作经验质量"
            )
        ]
    )
    
    # 运行评估
    node = CandidateEvaluationNode()
    evaluations = await node.run_standalone(candidates, job_requirement, scoring_dimensions)
    
    for eval in evaluations:
        print(f"候选人: {eval.candidate_name}")
        print(f"总分: {eval.overall_score}")
        print(f"推荐: {eval.recommendation}")
        print("---")

if __name__ == "__main__":
    asyncio.run(main())