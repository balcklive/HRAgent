# Author: Peng Fei

"""
Report Generation Node Prompts
This file contains all prompts and templates used by the report generation node.
"""

# Report header template
REPORT_HEADER_TEMPLATE = """# Candidate Evaluation Report

**Position**: {position}  
**Number of Candidates**: {candidate_count}  
**Generated Time**: {current_time}

## Recruitment Requirements Summary

**Must-Have Requirements**:
{must_have_formatted}

**Nice-to-Have Requirements**:
{nice_to_have_formatted}

**Deal-Breaker Requirements**:
{deal_breaker_formatted}"""

# Basic info table template
BASIC_INFO_TABLE_TEMPLATE = """## Basic Information Comparison

{table_content}"""

# Dimension table template
DIMENSION_TABLE_TEMPLATE = """## {dimension_name} ({weight_percentage} weight)

{table_content}"""

# Overall ranking table template
OVERALL_RANKING_TEMPLATE = """## Overall Scoring and Ranking

{table_content}"""

# Recommendation summary template
RECOMMENDATION_SUMMARY_TEMPLATE = """## Recommendation Summary

{summary_content}"""

# Recommendation status constants
RECOMMENDATION_STATUS = {
    "RECOMMENDED": "Recommended ✓",
    "CONSIDER": "Consider ⚠️", 
    "NOT_RECOMMENDED": "Not Recommended ❌"
}

# Score thresholds
SCORE_THRESHOLDS = {
    "RECOMMENDED": 7.0,
    "CONSIDER": 5.0,
    "NOT_RECOMMENDED": 0.0
} 