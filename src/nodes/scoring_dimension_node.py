# Author: Peng Fei

import asyncio
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from src.models import JobRequirement, ScoringDimensions
from src.prompts import (
    SCORING_DIMENSION_SYSTEM_PROMPT,
    SCORING_DIMENSION_PROMPT_TEMPLATE
)
import json
import re

class ScoringDimensionNode:
    """评分维度生成节点 - 根据招聘需求生成个性化评分维度"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.system_prompt = SCORING_DIMENSION_SYSTEM_PROMPT
        
    def process(self, job_requirement: JobRequirement) -> Dict[str, Any]:
        """处理评分维度生成"""
        try:
            # 构建提示
            prompt = self._build_prompt(job_requirement)
            
            # 调用LLM生成评分维度
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # 解析响应
            dimensions_data = self._parse_dimensions(response.content)
            
            # 验证和调整
            dimensions_data = self._validate_dimensions(dimensions_data)
            
            # 创建ScoringDimensions对象
            scoring_dimensions = ScoringDimensions(**dimensions_data)
            
            return {
                "status": "success",
                "scoring_dimensions": scoring_dimensions,
                "raw_response": response.content
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "scoring_dimensions": self._get_default_dimensions()
            }
    
    def _build_prompt(self, job_requirement: JobRequirement) -> str:
        """构建生成评分维度的提示"""
        must_have_formatted = self._format_requirements(job_requirement.must_have)
        nice_to_have_formatted = self._format_requirements(job_requirement.nice_to_have)
        deal_breaker_formatted = self._format_requirements(job_requirement.deal_breaker)
        
        return SCORING_DIMENSION_PROMPT_TEMPLATE.format(
            position=job_requirement.position,
            industry=job_requirement.industry or '未指定',
            min_years_experience=job_requirement.min_years_experience or '未指定',
            must_have_formatted=must_have_formatted,
            nice_to_have_formatted=nice_to_have_formatted,
            deal_breaker_formatted=deal_breaker_formatted
        )
    
    def _format_requirements(self, requirements: List[str]) -> str:
        """格式化需求列表"""
        if not requirements:
            return "- 无"
        return "\n".join(f"- {req}" for req in requirements)
    
    def _parse_dimensions(self, response: str) -> Dict[str, Any]:
        """解析LLM响应中的评分维度"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # 如果没有```json```标记，尝试直接解析
            # 查找看起来像JSON的部分
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
            
            # 如果都失败，返回默认维度
            return self._get_default_dimensions()
            
        except json.JSONDecodeError:
            return self._get_default_dimensions()
    
    def _validate_dimensions(self, dimensions_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证和调整评分维度"""
        dimensions = dimensions_data.get("dimensions", [])
        
        # 验证权重总和
        total_weight = sum(d.get("weight", 0) for d in dimensions)
        if abs(total_weight - 1.0) > 0.01:
            # 重新调整权重
            for dim in dimensions:
                dim["weight"] = dim.get("weight", 0) / total_weight
        
        # 确保必要字段存在
        for dim in dimensions:
            if "name" not in dim:
                dim["name"] = "未命名维度"
            if "fields" not in dim:
                dim["fields"] = ["待定义"]
            if "description" not in dim:
                dim["description"] = "评分维度描述"
        
        return {"dimensions": dimensions}
    
    def _get_default_dimensions(self) -> Dict[str, Any]:
        """获取默认评分维度"""
        return {
            "dimensions": [
                {
                    "name": "基础信息",
                    "weight": 0.1,
                    "fields": ["姓名", "经验年限", "当前职位", "教育背景", "所在地"],
                    "description": "候选人基本信息评估"
                },
                {
                    "name": "技能匹配",
                    "weight": 0.4,
                    "fields": ["核心技能", "技术深度", "技术广度"],
                    "description": "技术技能与职位要求匹配度"
                },
                {
                    "name": "经验评估",
                    "weight": 0.3,
                    "fields": ["工作经验", "项目经验", "行业经验"],
                    "description": "工作经验质量和相关性"
                },
                {
                    "name": "软技能",
                    "weight": 0.2,
                    "fields": ["沟通能力", "领导力", "团队合作"],
                    "description": "软技能和综合素质评估"
                }
            ]
        }
    
    def run_standalone(self, job_requirement: JobRequirement) -> ScoringDimensions:
        """独立运行模式"""
        result = self.process(job_requirement)
        
        if result["status"] == "success":
            scoring_dimensions = result["scoring_dimensions"]
            print("=== 评分维度生成完成 ===")
            print(f"职位: {job_requirement.position}")
            print(f"维度数量: {len(scoring_dimensions.dimensions)}")
            
            for i, dimension in enumerate(scoring_dimensions.dimensions, 1):
                print(f"{i}. {dimension.name} ({dimension.weight:.0%}权重)")
                print(f"   字段: {', '.join(dimension.fields)}")
                print(f"   描述: {dimension.description}")
                print()
            
            return scoring_dimensions
        else:
            print(f"生成失败: {result['error']}")
            return result["scoring_dimensions"]

def main():
    """测试函数"""
    from src.models import JobRequirement
    
    # 示例招聘需求
    job_requirement = JobRequirement(
        position="高级Python开发工程师",
        industry="互联网",
        min_years_experience=5,
        must_have=["Python", "Django", "PostgreSQL", "5年以上经验"],
        nice_to_have=["Redis", "Docker", "微服务架构", "AWS"],
        deal_breaker=["无编程经验", "少于3年经验"]
    )
    
    node = ScoringDimensionNode()
    scoring_dimensions = node.run_standalone(job_requirement)
    
    if scoring_dimensions:
        print("评分维度生成成功！")

if __name__ == "__main__":
    main()