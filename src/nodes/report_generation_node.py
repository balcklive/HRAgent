from typing import List, Dict, Any, Optional
from src.models import (
    CandidateEvaluation,
    ScoringDimensions,
    JobRequirement,
    EvaluationStatus
)
import re
from datetime import datetime

class ReportGenerationNode:
    """报告生成节点 - 将评分结果转换为Markdown格式表格"""
    
    def __init__(self):
        pass
    
    def process(self, 
                evaluations: List[CandidateEvaluation],
                job_requirement: JobRequirement,
                scoring_dimensions: ScoringDimensions) -> Dict[str, Any]:
        """处理报告生成"""
        try:
            if not evaluations:
                return {
                    "status": "error",
                    "error": "没有候选人评价数据",
                    "report": ""
                }
            
            # 生成报告
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
    
    def _generate_markdown_report(self, 
                                evaluations: List[CandidateEvaluation],
                                job_requirement: JobRequirement,
                                scoring_dimensions: ScoringDimensions) -> str:
        """生成Markdown格式报告"""
        report_parts = []
        
        # 1. 报告头部信息
        report_parts.append(self._generate_header(job_requirement, len(evaluations)))
        
        # 2. 基本信息表格
        report_parts.append(self._generate_basic_info_table(evaluations))
        
        # 3. 各维度评分表格
        for dimension in scoring_dimensions.dimensions:
            table = self._generate_dimension_table(evaluations, dimension)
            if table:
                report_parts.append(table)
        
        # 4. 总体评分和排名
        report_parts.append(self._generate_overall_ranking_table(evaluations))
        
        # 5. 推荐总结
        report_parts.append(self._generate_recommendation_summary(evaluations))
        
        return "\n\n".join(report_parts)
    
    def _generate_header(self, job_requirement: JobRequirement, candidate_count: int) -> str:
        """生成报告头部"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        header = f"""# 候选人评估报告

**职位名称**: {job_requirement.position}  
**候选人数量**: {candidate_count}  
**生成时间**: {current_time}

## 招聘需求概要

**必要条件**:
{self._format_requirement_list(job_requirement.must_have)}

**加分条件**:
{self._format_requirement_list(job_requirement.nice_to_have)}

**排除条件**:
{self._format_requirement_list(job_requirement.deal_breaker)}"""
        
        return header
    
    def _format_requirement_list(self, requirements: List[str]) -> str:
        """格式化需求列表"""
        if not requirements:
            return "- 无"
        return "\n".join(f"- {req}" for req in requirements)
    
    def _generate_basic_info_table(self, evaluations: List[CandidateEvaluation]) -> str:
        """生成基本信息表格"""
        if not evaluations:
            return ""
        
        # 表头
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
        
        # 推荐状态行
        recommendations = []
        for eval in evaluations:
            if eval.overall_score >= 7:
                recommendations.append("推荐 ✓")
            elif eval.overall_score >= 5:
                recommendations.append("考虑 ⚠️")
            else:
                recommendations.append("不推荐 ❌")
        
        rows.append("| **Recommendation** | " + " | ".join(recommendations) + " |")
        
        # 尝试从维度评分中提取基本信息
        basic_info_fields = ["姓名", "经验年限", "当前职位", "教育背景", "所在地"]
        
        for field in basic_info_fields:
            field_data = self._extract_field_data(evaluations, field)
            if field_data:
                rows.append(f"| **{field}** | " + " | ".join(field_data) + " |")
        
        table = "\n".join([header, separator] + rows)
        return f"## 基本信息对比\n\n{table}"
    
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
        
        # 表头
        candidates = [f"**{eval.candidate_name}**" for eval in evaluations]
        header = f"| **{dimension.name}** | " + " | ".join(candidates) + " |"
        separator = "|" + "|".join(["---"] * (len(candidates) + 1)) + "|"
        
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
        return f"## {dimension.name} ({dimension.weight:.0%}权重)\n\n{table}"
    
    def _generate_overall_ranking_table(self, evaluations: List[CandidateEvaluation]) -> str:
        """生成总体排名表格"""
        if not evaluations:
            return ""
        
        header = "| **排名** | **候选人** | **总分** | **推荐状态** | **主要优势** | **主要劣势** |"
        separator = "|------|---------|--------|------------|------------|------------|"
        
        rows = []
        for eval in evaluations:
            ranking = eval.ranking
            name = eval.candidate_name
            score = f"{eval.overall_score:.1f}/10"
            
            # 推荐状态
            if eval.overall_score >= 7:
                status = "推荐 ✓"
            elif eval.overall_score >= 5:
                status = "考虑 ⚠️"
            else:
                status = "不推荐 ❌"
            
            # 主要优势（取前2个）
            strengths = ", ".join(eval.strengths[:2]) if eval.strengths else "无"
            
            # 主要劣势（取前2个）
            weaknesses = ", ".join(eval.weaknesses[:2]) if eval.weaknesses else "无"
            
            rows.append(f"| {ranking} | {name} | {score} | {status} | {strengths} | {weaknesses} |")
        
        table = "\n".join([header, separator] + rows)
        return f"## 总体排名\n\n{table}"
    
    def _generate_recommendation_summary(self, evaluations: List[CandidateEvaluation]) -> str:
        """生成推荐总结"""
        if not evaluations:
            return ""
        
        summary_parts = ["## 推荐总结\n"]
        
        # 统计推荐情况
        recommended = [e for e in evaluations if e.overall_score >= 7]
        consider = [e for e in evaluations if 5 <= e.overall_score < 7]
        not_recommended = [e for e in evaluations if e.overall_score < 5]
        
        summary_parts.append(f"### 推荐情况统计")
        summary_parts.append(f"- **强烈推荐**: {len(recommended)} 人")
        summary_parts.append(f"- **可以考虑**: {len(consider)} 人")
        summary_parts.append(f"- **不推荐**: {len(not_recommended)} 人")
        
        # 前3名候选人详细推荐
        if evaluations:
            summary_parts.append(f"\n### 重点推荐候选人")
            for i, eval in enumerate(evaluations[:3], 1):
                summary_parts.append(f"\n**{i}. {eval.candidate_name}** (总分: {eval.overall_score:.1f}/10)")
                summary_parts.append(f"- **推荐理由**: {eval.recommendation}")
                if eval.strengths:
                    summary_parts.append(f"- **主要优势**: {', '.join(eval.strengths)}")
                if eval.weaknesses:
                    summary_parts.append(f"- **需要关注**: {', '.join(eval.weaknesses)}")
        
        return "\n".join(summary_parts)
    
    def _extract_field_data(self, evaluations: List[CandidateEvaluation], field_name: str) -> List[str]:
        """从评分中提取字段数据"""
        field_data = []
        for eval in evaluations:
            found_data = "N/A"
            for dim_score in eval.dimension_scores:
                if field_name in dim_score.details:
                    found_data = self._format_field_detail(dim_score.details[field_name])
                    break
            field_data.append(found_data)
        return field_data
    
    def _format_field_detail(self, detail: str) -> str:
        """格式化字段详情"""
        if not detail:
            return "N/A"
        
        # 简化显示，如果太长则截取
        if len(detail) > 20:
            return detail[:17] + "..."
        
        return detail
    
    def run_standalone(self, 
                      evaluations: List[CandidateEvaluation],
                      job_requirement: JobRequirement,
                      scoring_dimensions: ScoringDimensions) -> str:
        """独立运行模式"""
        print("=== 生成候选人评估报告 ===")
        print(f"候选人数量: {len(evaluations)}")
        
        result = self.process(evaluations, job_requirement, scoring_dimensions)
        
        if result["status"] == "success":
            print("报告生成成功!")
            print(f"候选人数量: {result['candidate_count']}")
            print(f"生成时间: {result['generated_at']}")
            
            # 显示报告预览
            report_lines = result["report"].split('\n')
            print("\n=== 报告预览 (前30行) ===")
            for line in report_lines[:30]:
                print(line)
            
            if len(report_lines) > 30:
                print(f"\n... 还有 {len(report_lines) - 30} 行内容")
            
            return result["report"]
        else:
            print(f"报告生成失败: {result['error']}")
            return ""
    
    def save_report(self, report: str, filename: str = None) -> str:
        """保存报告到文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"candidate_evaluation_report_{timestamp}.md"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            return filename
        except Exception as e:
            print(f"保存报告失败: {str(e)}")
            return ""


# 使用示例
def main():
    from src.models import (
        CandidateEvaluation, DimensionScore, JobRequirement, 
        ScoringDimensions, ScoringDimension, EvaluationStatus
    )
    
    # 示例数据
    job_requirement = JobRequirement(
        position="高级后端开发工程师",
        must_have=["5年以上Node.js经验", "PostgreSQL数据库"],
        nice_to_have=["微服务架构", "AWS云平台"],
        deal_breaker=["少于3年经验"]
    )
    
    scoring_dimensions = ScoringDimensions(
        dimensions=[
            ScoringDimension(name="技能匹配", weight=0.4, fields=["Node.js", "PostgreSQL", "微服务"]),
            ScoringDimension(name="经验评估", weight=0.3, fields=["工作年限", "项目经验"]),
            ScoringDimension(name="基础信息", weight=0.3, fields=["教育背景", "所在地"])
        ]
    )
    
    # 示例评价数据
    evaluations = [
        CandidateEvaluation(
            candidate_id="1",
            candidate_name="张三",
            dimension_scores=[
                DimensionScore(
                    dimension_name="技能匹配",
                    score=8.5,
                    status=EvaluationStatus.PASS,
                    details={"Node.js": "6年经验", "PostgreSQL": "熟练使用"},
                    comments="技能匹配度高"
                )
            ],
            overall_score=8.0,
            recommendation="强烈推荐",
            strengths=["技术能力强", "经验丰富"],
            weaknesses=["沟通能力待提升"],
            ranking=1
        )
    ]
    
    node = ReportGenerationNode()
    report = node.run_standalone(evaluations, job_requirement, scoring_dimensions)
    
    if report:
        filename = node.save_report(report)
        print(f"\\n报告已保存至: {filename}")

if __name__ == "__main__":
    main()