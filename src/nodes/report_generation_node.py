# Author: Peng Fei

from typing import List, Dict, Any, Optional, Callable
from src.models import (
    CandidateEvaluation,
    ScoringDimensions,
    JobRequirement,
    EvaluationStatus
)
from src.prompts import (
    REPORT_HEADER_TEMPLATE,
    BASIC_INFO_TABLE_TEMPLATE,
    DIMENSION_TABLE_TEMPLATE,
    OVERALL_RANKING_TEMPLATE,
    RECOMMENDATION_SUMMARY_TEMPLATE,
    RECOMMENDATION_STATUS,
    SCORE_THRESHOLDS
)
import re
from datetime import datetime

class ReportGenerationNode:
    """Report generation node - Convert evaluation results to Markdown format tables"""
    
    def __init__(self):
        pass
    
    def process(self, 
                evaluations: List[CandidateEvaluation],
                job_requirement: JobRequirement,
                scoring_dimensions: ScoringDimensions) -> Dict[str, Any]:
        """Process report generation"""
        try:
            if not evaluations:
                return {
                    "status": "error",
                    "error": "No candidate evaluation data",
                    "report": ""
                }
            
            # Generate report
            report = self._generate_markdown_report(evaluations, job_requirement, scoring_dimensions)
            
            return {
                "status": "success",
                "report": report,
                "candidate_count": len(evaluations),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "report": ""
            }

    async def process_stream(self, 
                            evaluations: List[CandidateEvaluation],
                            job_requirement: JobRequirement,
                            scoring_dimensions: ScoringDimensions,
                            progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Process report generation（带进度流式输出）"""
        try:
            if progress_callback:
                await progress_callback({
                    "stage": "report_generation",
                    "message": "Starting to generate candidate evaluation report",
                    "progress": 90,
                    "total_items": 1,
                    "completed_items": 0
                })
            
            if not evaluations:
                return {
                    "status": "error",
                    "error": "No candidate evaluation data",
                    "report": ""
                }
            
            if progress_callback:
                await progress_callback({
                    "stage": "report_generation",
                    "message": "Analyzing candidate data",
                    "progress": 92,
                    "current_item": "Data analysis"
                })
            
            # Generate report（在线程池中执行以避免阻塞）
            import asyncio
            loop = asyncio.get_event_loop()
            
            if progress_callback:
                await progress_callback({
                    "stage": "report_generation",
                    "message": "Generating Markdown report",
                    "progress": 95,
                    "current_item": "Report generation"
                })
            
            report = await loop.run_in_executor(
                None, 
                self._generate_markdown_report, 
                evaluations, 
                job_requirement, 
                scoring_dimensions
            )
            
            if progress_callback:
                await progress_callback({
                    "stage": "report_generation",
                    "message": "Report generation completed",
                    "progress": 98,
                    "current_item": "Report completed"
                })
            
            return {
                "status": "success",
                "report": report,
                "candidate_count": len(evaluations),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            if progress_callback:
                await progress_callback({
                    "stage": "report_generation",
                    "message": f"Report generation failed: {str(e)}",
                    "progress": 90,
                    "error": str(e)
                })
            
            return {
                "status": "error",
                "error": str(e),
                "report": ""
            }
    
    def _generate_markdown_report(self, 
                                evaluations: List[CandidateEvaluation],
                                job_requirement: JobRequirement,
                                scoring_dimensions: ScoringDimensions) -> str:
        """Generate Markdown format report"""
        report_parts = []
        
        # 1. Report header information
        report_parts.append(self._generate_header(job_requirement, len(evaluations)))
        
        # 2. Simplified candidate evaluation summary table
        report_parts.append(self._generate_simplified_summary_table(evaluations, scoring_dimensions))
        
        # 3. Recommendation summary
        report_parts.append(self._generate_recommendation_summary(evaluations))
        
        return "\n\n".join(report_parts)
    
    def _generate_simplified_summary_table(self, evaluations: List[CandidateEvaluation], scoring_dimensions: ScoringDimensions) -> str:
        """Generate simplified candidate evaluation summary table"""
        if not evaluations:
            return ""
        
        # Table header
        header = "| Candidate | Overall Score | Technical Skills | Project Experience | Team Management | Key Strengths | Key Weaknesses |"
        separator = "|--------|----------|----------|----------|----------|----------|----------|"
        
        rows = []
        
        for eval in evaluations:
            # Candidate name (bold for top 3)
            if eval.ranking == 1:
                candidate_name = f"**{eval.candidate_name}**"
            else:
                candidate_name = f"**{eval.candidate_name}**"
            
            # Overall score (bold)
            overall_score = f"**{eval.overall_score:.1f}/10**"
            
            # Extract dimension scores
            tech_score = self._extract_dimension_score(eval, ["技能匹配", "技术能力", "技术技能"])
            project_score = self._extract_dimension_score(eval, ["经验评估", "项目经验", "工作经验"])
            management_score = self._extract_dimension_score(eval, ["软技能", "团队管理", "管理能力"])
            
            # Key strengths (top 2)
            strengths = "，".join(eval.strengths[:2]) if eval.strengths else "Basic skills"
            
            # Key weaknesses (top 1)
            weaknesses = eval.weaknesses[0] if eval.weaknesses else "To be understood"
            
            row = f"| {candidate_name} | {overall_score} | {tech_score}/10 | {project_score}/10 | {management_score}/10 | {strengths} | {weaknesses} |"
            rows.append(row)
        
        table = "\n".join([header, separator] + rows)
        
        # Add recommendation results
        recommendation_results = "\n\n**Recommendation Results:**\n"
        for i, eval in enumerate(evaluations[:3]):  # Only show top 3
            if i == 0:
                emoji = "🥇"
                desc = "Strongly recommended, best candidate"
            elif i == 1:
                emoji = "🥈"
                desc = "Recommended, second choice candidate"
            else:
                emoji = "🥉"
                desc = "Consider, alternative candidate"
            
            if eval.overall_score >= SCORE_THRESHOLDS["RECOMMENDED"]:
                recommendation_results += f"{emoji} **{eval.candidate_name}** - {desc}\n"
            elif eval.overall_score >= SCORE_THRESHOLDS["CONSIDER"]:
                recommendation_results += f"⚠️ **{eval.candidate_name}** - Consider with caution, needs further evaluation\n"
            else:
                recommendation_results += f"❌ **{eval.candidate_name}** - Not recommended, does not meet requirements\n"
        
        # Handle remaining candidates
        for eval in evaluations[3:]:
            if eval.overall_score >= SCORE_THRESHOLDS["RECOMMENDED"]:
                recommendation_results += f"✅ **{eval.candidate_name}** - Recommended\n"
            elif eval.overall_score >= SCORE_THRESHOLDS["CONSIDER"]:
                recommendation_results += f"⚠️ **{eval.candidate_name}** - Consider with caution\n"
            else:
                recommendation_results += f"❌ **{eval.candidate_name}** - Not recommended\n"
        
        return f"## Candidate Evaluation Summary\n\n{table}{recommendation_results}"
    
    def _extract_dimension_score(self, evaluation: CandidateEvaluation, dimension_names: List[str]) -> str:
        """Extract dimension score"""
        for dimension_name in dimension_names:
            for score in evaluation.dimension_scores:
                if dimension_name in score.dimension_name:
                    return f"{score.score:.1f}"
        return "N/A"
    
    def _generate_header(self, job_requirement: JobRequirement, candidate_count: int) -> str:
        """Generate report header"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        must_have_formatted = self._format_requirement_list(job_requirement.must_have)
        nice_to_have_formatted = self._format_requirement_list(job_requirement.nice_to_have)
        deal_breaker_formatted = self._format_requirement_list(job_requirement.deal_breaker)
        
        return REPORT_HEADER_TEMPLATE.format(
            position=job_requirement.position,
            candidate_count=candidate_count,
            current_time=current_time,
            must_have_formatted=must_have_formatted,
            nice_to_have_formatted=nice_to_have_formatted,
            deal_breaker_formatted=deal_breaker_formatted
        )
    
    def _format_requirement_list(self, requirements: List[str]) -> str:
        """Format requirement list"""
        if not requirements:
            return "- None"
        return "\n".join(f"- {req}" for req in requirements)
    
    def _generate_basic_info_table(self, evaluations: List[CandidateEvaluation]) -> str:
        """生成基本信息表格"""
        if not evaluations:
            return ""
        
        # Table header
        candidates = [f"**{eval.candidate_name}**" for eval in evaluations]
        header = "| **Basic Info** | " + " | ".join(candidates) + " |"
        separator = "|" + "|".join(["---"] * (len(candidates) + 1)) + "|"
        
        rows = []
        
        # 排名行
        rankings = [str(eval.ranking) for eval in evaluations]
        rows.append("| **Ranking** | " + " | ".join(rankings) + " |")
        
        # 总分行
        scores = [f"{eval.overall_score:.1f}/10" for eval in evaluations]
        rows.append("| **Overall Score** | " + " | ".join(scores) + " |")
        
        # Recommended状态行
        recommendations = []
        for eval in evaluations:
            if eval.overall_score >= SCORE_THRESHOLDS["RECOMMENDED"]:
                recommendations.append(RECOMMENDATION_STATUS["RECOMMENDED"])
            elif eval.overall_score >= SCORE_THRESHOLDS["CONSIDER"]:
                recommendations.append(RECOMMENDATION_STATUS["CONSIDER"])
            else:
                recommendations.append(RECOMMENDATION_STATUS["NOT_RECOMMENDED"])
        
        rows.append("| **Recommendation** | " + " | ".join(recommendations) + " |")
        
        # 尝试从维度评分中提取基本信息
        basic_info_fields = ["姓名", "经验年限", "当前职位", "教育背景", "所在地"]
        
        for field in basic_info_fields:
            field_data = self._extract_field_data(evaluations, field)
            if field_data:
                rows.append(f"| **{field}** | " + " | ".join(field_data) + " |")
        
        table = "\n".join([header, separator] + rows)
        return BASIC_INFO_TABLE_TEMPLATE.format(table_content=table)
    
    def _generate_dimension_table(self, 
                                evaluations: List[CandidateEvaluation], 
                                dimension) -> str:
        """生成维度评分表格"""
        if not evaluations:
            return ""
        
        # 查找该维度的评分
        dimension_scores = []
        for eval in evaluations:
            dim_score = None
            for score in eval.dimension_scores:
                if score.dimension_name == dimension.name:
                    dim_score = score
                    break
            dimension_scores.append(dim_score)
        
        # 如果没有找到该维度的评分，跳过
        if not any(score for score in dimension_scores):
            return ""
        
        # Table header
        candidates = [f"**{eval.candidate_name}**" for eval in evaluations]
        header = f"| **{dimension.name}** | " + " | ".join(candidates) + " |"
        separator = "|" + "|".join(["---"] * (len(candidates) + 1)) + " |"
        
        rows = []
        
        # 维度总分行
        scores = []
        for score in dimension_scores:
            if score:
                score_str = f"{score.score:.1f} {score.status.value}"
                scores.append(score_str)
            else:
                scores.append("N/A")
        
        rows.append(f"| **{dimension.name} Score** | " + " | ".join(scores) + " |")
        
        # 为每个字段生成行
        for field in dimension.fields:
            field_data = []
            for score in dimension_scores:
                if score and field in score.details:
                    detail = score.details[field]
                    # 简化显示，只显示关键信息
                    field_data.append(self._format_field_detail(detail))
                else:
                    field_data.append("N/A")
            
            rows.append(f"| **{field}** | " + " | ".join(field_data) + " |")
        
        table = "\n".join([header, separator] + rows)
        weight_percentage = f"{dimension.weight:.0%}"
        return DIMENSION_TABLE_TEMPLATE.format(
            dimension_name=dimension.name,
            weight_percentage=weight_percentage,
            table_content=table
        )
    
    def _generate_overall_ranking_table(self, evaluations: List[CandidateEvaluation]) -> str:
        """生成总体排名表格"""
        if not evaluations:
            return ""
        
        # Table header
        header = "| **Rank** | **Candidate** | **Score** | **Status** | **Strengths** | **Weaknesses** |"
        separator = "|" + "|".join(["---"] * 6) + "|"
        
        rows = []
        for eval in evaluations:
            # Recommended状态
            if eval.overall_score >= SCORE_THRESHOLDS["RECOMMENDED"]:
                status = RECOMMENDATION_STATUS["RECOMMENDED"]
            elif eval.overall_score >= SCORE_THRESHOLDS["CONSIDER"]:
                status = RECOMMENDATION_STATUS["CONSIDER"]
            else:
                status = RECOMMENDATION_STATUS["NOT_RECOMMENDED"]
            
            # 优势和劣势（限制长度）
            strengths = ", ".join(eval.strengths[:2]) if eval.strengths else "无"
            weaknesses = ", ".join(eval.weaknesses[:2]) if eval.weaknesses else "无"
            
            row = f"| {eval.ranking} | {eval.candidate_name} | {eval.overall_score:.1f}/10 | {status} | {strengths} | {weaknesses} |"
            rows.append(row)
        
        table = "\n".join([header, separator] + rows)
        return OVERALL_RANKING_TEMPLATE.format(table_content=table)
    
    def _generate_recommendation_summary(self, evaluations: List[CandidateEvaluation]) -> str:
        """生成Recommended总结"""
        if not evaluations:
            return ""
        
        # 统计Recommended情况
        recommended = [e for e in evaluations if e.overall_score >= SCORE_THRESHOLDS["RECOMMENDED"]]
        consider = [e for e in evaluations if SCORE_THRESHOLDS["CONSIDER"] <= e.overall_score < SCORE_THRESHOLDS["RECOMMENDED"]]
        not_recommended = [e for e in evaluations if e.overall_score < SCORE_THRESHOLDS["CONSIDER"]]
        
        summary_parts = []
        summary_parts.append(f"**Evaluation Summary:**")
        summary_parts.append(f"- Total candidates: {len(evaluations)} people")
        summary_parts.append(f"- Recommended: {len(recommended)} people")
        summary_parts.append(f"- Consider: {len(consider)} people")
        summary_parts.append(f"- Not recommended: {len(not_recommended)} people")
        summary_parts.append("")
        
        if recommended:
            summary_parts.append("**Recommended candidates:**")
            for eval in recommended:
                summary_parts.append(f"- {eval.candidate_name} (Score:  {eval.overall_score:.1f})")
            summary_parts.append("")
        
        if consider:
            summary_parts.append("**Consider candidates:**")
            for eval in consider:
                summary_parts.append(f"- {eval.candidate_name} (Score:  {eval.overall_score:.1f})")
            summary_parts.append("")
        
        # Add overall recommendations
        if recommended:
            summary_parts.append("**Recommendations:**")
            summary_parts.append("1. Prioritize interviews for recommended candidates")
            if consider:
                summary_parts.append("2. Consider interviewing some candidates under consideration")
            summary_parts.append("3. Make final decisions based on interview results")
        else:
            summary_parts.append("**Recommendations:**")
            summary_parts.append("1. Current candidates have low overall match")
            summary_parts.append("2. Recommend expanding recruitment scope or adjusting requirements")
            summary_parts.append("3. Consider interviewing some candidates under consideration")
        
        summary_content = "\n".join(summary_parts)
        return RECOMMENDATION_SUMMARY_TEMPLATE.format(summary_content=summary_content)
    
    def _extract_field_data(self, evaluations: List[CandidateEvaluation], field_name: str) -> List[str]:
        """从维度评分中提取字段数据"""
        field_data = []
        for eval in evaluations:
            found = False
            for score in eval.dimension_scores:
                if field_name in score.details:
                    field_data.append(self._format_field_detail(score.details[field_name]))
                    found = True
                    break
            if not found:
                field_data.append("N/A")
        return field_data
    
    def _format_field_detail(self, detail: str) -> str:
        """格式化字段详情"""
        if not detail:
            return "N/A"
        
        # 限制长度，避免表格过宽
        if len(detail) > 50:
            return detail[:47] + "..."
        return detail
    
    def run_standalone(self, 
                      evaluations: List[CandidateEvaluation],
                      job_requirement: JobRequirement,
                      scoring_dimensions: ScoringDimensions) -> str:
        """独立运行模式"""
        result = self.process(evaluations, job_requirement, scoring_dimensions)
        
        if result["status"] == "success":
            print(f"Report generation completed: {result['candidate_count']} 个candidates")
            return result["report"]
        else:
            print(f"Report generation failed: {result['error']}")
            return ""
    
    def save_report(self, report: str, filename: str = None) -> str:
        """保存报告到文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"candidate_evaluation_report_{timestamp}.md"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"报告已保存到: {filename}")
            return filename
        except Exception as e:
            print(f"保存报告失败: {str(e)}")
            return ""

def main():
    """测试函数"""
    from src.models import CandidateEvaluation, JobRequirement, ScoringDimensions, ScoringDimension, DimensionScore, EvaluationStatus
    
    # 创建测试数据
    evaluations = [
        CandidateEvaluation(
            candidate_id="1",
            candidate_name="张三",
            dimension_scores=[
                DimensionScore(
                    dimension_name="技能匹配",
                    score=8.5,
                    status=EvaluationStatus.PASS,
                    details={"Python": "熟练", "Django": "熟练"},
                    comments="技能匹配度高"
                )
            ],
            overall_score=8.5,
            recommendation="Recommended面试",
            strengths=["技术能力强", "经验丰富"],
            weaknesses=["沟通能力待提升"]
        ),
        CandidateEvaluation(
            candidate_id="2", 
            candidate_name="李四",
            dimension_scores=[
                DimensionScore(
                    dimension_name="技能匹配",
                    score=6.0,
                    status=EvaluationStatus.WARNING,
                    details={"Python": "一般", "Django": "一般"},
                    comments="技能匹配度一般"
                )
            ],
            overall_score=6.0,
            recommendation="可考虑",
            strengths=["学习能力强"],
            weaknesses=["经验不足"]
        )
    ]
    
    job_requirement = JobRequirement(
        position="Python开发工程师",
        must_have=["Python", "Django"],
        nice_to_have=["Redis", "Docker"],
        deal_breaker=["无编程经验"]
    )
    
    scoring_dimensions = ScoringDimensions(
        dimensions=[
            ScoringDimension(
                name="技能匹配",
                weight=0.6,
                fields=["Python", "Django"],
                description="技术技能匹配度"
            )
        ]
    )
    
    # Generate report
    node = ReportGenerationNode()
    report = node.run_standalone(evaluations, job_requirement, scoring_dimensions)
    
    if report:
        print("=== 生成的报告 ===")
        print(report)
        
        # 保存报告
        node.save_report(report)

if __name__ == "__main__":
    main()