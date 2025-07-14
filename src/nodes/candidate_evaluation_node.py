import asyncio
from typing import List, Dict, Any, Optional
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
        self.system_prompt = self._build_system_prompt()
        
    def _build_system_prompt(self) -> str:
        return """你是一个专业的HR评分专家，负责根据招聘需求和评分维度对候选人进行客观、公正的评分。

**评分原则：**
1. 严格按照10分制评分 (0-10分)
2. 基于客观事实，避免主观偏见
3. 必要条件不满足应严格扣分
4. 加分条件满足应适当加分
5. 排除条件触发应严重扣分

**评分标准：**
- 9-10分: 完全符合要求，表现优秀
- 7-8分: 基本符合要求，表现良好
- 5-6分: 部分符合要求，表现一般
- 3-4分: 不太符合要求，表现较差
- 1-2分: 基本不符合要求，表现很差
- 0分: 完全不符合要求或触发排除条件

**评估状态标记：**
- ✓ (PASS): 7分以上，符合要求
- ⚠️ (WARNING): 4-6分，需要注意
- ❌ (FAIL): 3分以下，不符合要求

**输出格式：**
对每个维度进行评分，输出JSON格式：
```json
{
    "dimension_scores": [
        {
            "dimension_name": "维度名称",
            "score": 8.5,
            "status": "✓",
            "details": {
                "字段1": "评分理由",
                "字段2": "评分理由"
            },
            "comments": "总体评价"
        }
    ],
    "overall_score": 7.8,
    "recommendation": "推荐/不推荐的理由",
    "strengths": ["优势1", "优势2"],
    "weaknesses": ["劣势1", "劣势2"]
}
```

**评分要求：**
1. 必须为每个维度的每个字段提供评分依据
2. 总分为各维度加权平均
3. 推荐建议要具体明确
4. 优势和劣势要客观真实
5. 如果信息不足，在comments中说明"""

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
        
        return f"""
请对以下候选人进行评分：

**招聘需求：**
{requirements_info}

**评分维度：**
{dimensions_info}

**候选人信息：**
{candidate_info}

请根据评分维度对候选人进行详细评分，特别注意：
1. 检查必要条件是否满足
2. 评估加分条件的匹配度
3. 识别是否触发排除条件
4. 为每个维度的每个字段提供具体评分理由

请输出JSON格式的评分结果：
"""
    
    def _format_candidate_info(self, candidate: CandidateProfile) -> str:
        """格式化候选人信息"""
        info = f"""
**基本信息：**
- 姓名: {candidate.basic_info.name}
- 工作年限: {candidate.basic_info.experience_years or '未知'}年
- 当前职位: {candidate.basic_info.current_role or '未知'}
- 当前公司: {candidate.basic_info.current_company or '未知'}
- 所在地: {candidate.basic_info.location or '未知'}
- 联系方式: {candidate.basic_info.email or '未知'}

**教育背景：**
"""
        if candidate.education:
            for edu in candidate.education:
                info += f"- {edu.degree} {edu.major} ({edu.school}, {edu.graduation_year or '未知'})\n"
        else:
            info += "- 无教育背景信息\n"
        
        info += "\n**工作经历：**\n"
        if candidate.work_experience:
            for work in candidate.work_experience:
                info += f"- {work.company} - {work.position} ({work.start_date} ~ {work.end_date or '至今'})\n"
                if work.description:
                    info += f"  {work.description}\n"
        else:
            info += "- 无工作经历信息\n"
        
        info += "\n**技能列表：**\n"
        if candidate.skills:
            for skill in candidate.skills:
                level = skill.level.value if skill.level else "未知"
                years = skill.years_experience or "未知"
                info += f"- {skill.name} ({level}, {years}年经验)\n"
        else:
            info += "- 无技能信息\n"
        
        if candidate.certifications:
            info += f"\n**认证证书：** {', '.join(candidate.certifications)}\n"
        
        if candidate.languages:
            info += f"\n**语言能力：** {', '.join(candidate.languages)}\n"
        
        if candidate.projects:
            info += f"\n**项目经验：** {', '.join(candidate.projects)}\n"
        
        return info
    
    def _format_requirements_info(self, job_requirement: JobRequirement) -> str:
        """格式化招聘需求信息"""
        info = f"""
- 职位: {job_requirement.position}
- 必要条件: {', '.join(job_requirement.must_have) if job_requirement.must_have else '无'}
- 加分条件: {', '.join(job_requirement.nice_to_have) if job_requirement.nice_to_have else '无'}
- 排除条件: {', '.join(job_requirement.deal_breaker) if job_requirement.deal_breaker else '无'}
"""
        return info
    
    def _format_dimensions_info(self, scoring_dimensions: ScoringDimensions) -> str:
        """格式化评分维度信息"""
        info = ""
        for dim in scoring_dimensions.dimensions:
            info += f"- {dim.name} (权重: {dim.weight:.1%})\n"
            info += f"  评分字段: {', '.join(dim.fields)}\n"
            if dim.description:
                info += f"  描述: {dim.description}\n"
            info += "\n"
        return info
    
    def _parse_evaluation_response(self, response: str) -> Dict[str, Any]:
        """解析评分响应"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # 如果没有标记，尝试寻找JSON结构
            lines = response.split('\n')
            json_start = -1
            json_end = -1
            brace_count = 0
            
            for i, line in enumerate(lines):
                if '{' in line and json_start == -1:
                    json_start = i
                    brace_count = line.count('{') - line.count('}')
                elif json_start != -1:
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0:
                        json_end = i
                        break
            
            if json_start != -1 and json_end != -1:
                json_str = '\n'.join(lines[json_start:json_end+1])
                return json.loads(json_str)
            
            return self._get_default_evaluation()
            
        except json.JSONDecodeError:
            return self._get_default_evaluation()
    
    def _get_default_evaluation(self) -> Dict[str, Any]:
        """获取默认评分"""
        return {
            "dimension_scores": [],
            "overall_score": 0.0,
            "recommendation": "评分解析失败",
            "strengths": [],
            "weaknesses": ["无法解析评分结果"]
        }
    
    def _create_candidate_evaluation(self, 
                                   candidate: CandidateProfile,
                                   evaluation_data: Dict[str, Any],
                                   scoring_dimensions: ScoringDimensions) -> CandidateEvaluation:
        """创建候选人评价对象"""
        # 处理维度评分
        dimension_scores = []
        for score_data in evaluation_data.get("dimension_scores", []):
            status_str = score_data.get("status", "⚠️")
            if status_str == "✓":
                status = EvaluationStatus.PASS
            elif status_str == "❌":
                status = EvaluationStatus.FAIL
            else:
                status = EvaluationStatus.WARNING
            
            dimension_score = DimensionScore(
                dimension_name=score_data.get("dimension_name", "未知维度"),
                score=max(0, min(10, score_data.get("score", 0))),  # 确保分数在0-10之间
                status=status,
                details=score_data.get("details", {}),
                comments=score_data.get("comments", "")
            )
            dimension_scores.append(dimension_score)
        
        # 计算总分（如果没有提供，则根据维度评分计算）
        overall_score = evaluation_data.get("overall_score", 0.0)
        if overall_score == 0 and dimension_scores:
            total_weighted_score = 0
            total_weight = 0
            for dim_score in dimension_scores:
                # 查找对应维度的权重
                for dim in scoring_dimensions.dimensions:
                    if dim.name == dim_score.dimension_name:
                        total_weighted_score += dim_score.score * dim.weight
                        total_weight += dim.weight
                        break
            
            if total_weight > 0:
                overall_score = total_weighted_score / total_weight
        
        # 确保总分在0-10之间
        overall_score = max(0, min(10, overall_score))
        
        # 创建评价对象
        evaluation = CandidateEvaluation(
            candidate_id=candidate.id,
            candidate_name=candidate.basic_info.name,
            dimension_scores=dimension_scores,
            overall_score=overall_score,
            recommendation=evaluation_data.get("recommendation", "无推荐意见"),
            strengths=evaluation_data.get("strengths", []),
            weaknesses=evaluation_data.get("weaknesses", [])
        )
        
        return evaluation
    
    async def run_standalone(self, 
                           candidates: List[CandidateProfile],
                           job_requirement: JobRequirement,
                           scoring_dimensions: ScoringDimensions) -> List[CandidateEvaluation]:
        """独立运行模式"""
        print("=== 候选人评分 ===")
        print(f"职位: {job_requirement.position}")
        print(f"候选人数量: {len(candidates)}")
        print(f"评分维度: {len(scoring_dimensions.dimensions)}")
        
        result = await self.process(candidates, job_requirement, scoring_dimensions)
        
        if result["status"] == "success":
            evaluations = result["evaluations"]
            print(f"\n=== 评分结果 ===")
            print(f"评分成功: {result['successful_evaluations']}/{result['total_candidates']}")
            
            print(f"\n=== 候选人排名 ===")
            for evaluation in evaluations:
                print(f"{evaluation.ranking}. {evaluation.candidate_name}")
                print(f"   总分: {evaluation.overall_score:.1f}/10")
                print(f"   推荐: {evaluation.recommendation}")
                print(f"   优势: {', '.join(evaluation.strengths[:2])}")
                print(f"   劣势: {', '.join(evaluation.weaknesses[:2])}")
                print()
            
            return evaluations
        else:
            print(f"评分失败: {result['error']}")
            return []


# 使用示例
async def main():
    from src.models import JobRequirement, ScoringDimensions, ScoringDimension
    
    # 示例数据
    job_requirement = JobRequirement(
        position="高级后端开发工程师",
        must_have=["5年以上Node.js经验", "PostgreSQL数据库"],
        nice_to_have=["微服务架构", "AWS云平台"],
        deal_breaker=["少于3年经验"]
    )
    
    scoring_dimensions = ScoringDimensions(
        dimensions=[
            ScoringDimension(name="技能匹配", weight=0.4, fields=["Node.js", "PostgreSQL"]),
            ScoringDimension(name="经验评估", weight=0.3, fields=["工作年限", "项目经验"]),
            ScoringDimension(name="基础信息", weight=0.3, fields=["教育背景", "沟通能力"])
        ]
    )
    
    # 这里需要实际的候选人数据
    candidates = []  # 从ResumeStructureNode获取
    
    node = CandidateEvaluationNode()
    evaluations = await node.run_standalone(candidates, job_requirement, scoring_dimensions)
    
    print(f"完成 {len(evaluations)} 个候选人的评分")

if __name__ == "__main__":
    asyncio.run(main())