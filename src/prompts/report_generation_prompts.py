# Author: Peng Fei

"""
Report Generation Node Prompts
This file contains all prompts and templates used by the report generation node.
"""

# Report header template
REPORT_HEADER_TEMPLATE = """# 候选人评估报告

**职位名称**: {position}  
**候选人数量**: {candidate_count}  
**生成时间**: {current_time}

## 招聘需求概要

**必要条件**:
{must_have_formatted}

**加分条件**:
{nice_to_have_formatted}

**排除条件**:
{deal_breaker_formatted}"""

# Basic info table template
BASIC_INFO_TABLE_TEMPLATE = """## 基本信息对比

{table_content}"""

# Dimension table template
DIMENSION_TABLE_TEMPLATE = """## {dimension_name} ({weight_percentage}权重)

{table_content}"""

# Overall ranking table template
OVERALL_RANKING_TEMPLATE = """## 总体评分和排名

{table_content}"""

# Recommendation summary template
RECOMMENDATION_SUMMARY_TEMPLATE = """## 推荐总结

{summary_content}"""

# Recommendation status constants
RECOMMENDATION_STATUS = {
    "RECOMMENDED": "推荐 ✓",
    "CONSIDER": "考虑 ⚠️", 
    "NOT_RECOMMENDED": "不推荐 ❌"
}

# Score thresholds
SCORE_THRESHOLDS = {
    "RECOMMENDED": 7.0,
    "CONSIDER": 5.0,
    "NOT_RECOMMENDED": 0.0
} 