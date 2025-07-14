from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from src.models import (
    JobRequirement,
    ScoringDimension,
    ScoringDimensions
)
import json
import re

class ScoringDimensionNode:
    """评分维度生成节点 - 基于招聘需求生成个性化评分维度"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.system_prompt = self._build_system_prompt()
        
    def _build_system_prompt(self) -> str:
        return """你是一个专业的HR评分系统设计师，负责根据招聘需求生成个性化的候选人评分维度。

**你的任务：**
1. 基于招聘需求，生成4-6个评分维度
2. 为每个维度分配合理的权重（总和为1.0）
3. 为每个维度定义具体的评分字段
4. 确保评分维度全面、合理、可操作

**评分维度设计原则：**
1. **基础信息** (10-15%权重): 姓名、经验年限、当前职位、教育背景、所在地等
2. **技能匹配** (30-40%权重): 根据职位要求的技术技能
3. **经验评估** (25-35%权重): 工作经验、项目经验、行业经验
4. **软技能** (10-20%权重): 沟通能力、领导力、团队合作
5. **加分项** (5-15%权重): 认证、开源贡献、语言能力等
6. **其他专业维度**: 根据具体职位需求添加

**输出格式要求：**
输出JSON格式的评分维度配置：
```json
{
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
            "fields": ["必要技能1", "必要技能2", "必要技能3"],
            "description": "技术技能与职位要求匹配度"
        }
    ]
}
```

**注意事项：**
- 权重总和必须为1.0
- 字段名要具体明确
- 根据不同职位类型调整维度重点
- 考虑must_have、nice_to_have、deal_breaker的影响"""

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
        return f"""
请基于以下招聘需求生成个性化的评分维度：

**职位信息：**
- 职位名称: {job_requirement.position}
- 行业: {job_requirement.industry or '未指定'}
- 最低经验要求: {job_requirement.min_years_experience or '未指定'}年

**必要条件 (must_have):**
{self._format_requirements(job_requirement.must_have)}

**加分条件 (nice_to_have):**
{self._format_requirements(job_requirement.nice_to_have)}

**排除条件 (deal_breaker):**
{self._format_requirements(job_requirement.deal_breaker)}

请根据这些信息生成合适的评分维度，特别注意：
1. 必要条件应该在技能匹配维度中占主要地位
2. 加分条件可以作为独立维度或加分项
3. 排除条件要在评分中体现负面影响
4. 根据职位类型调整各维度权重

请输出JSON格式的评分维度配置。
"""
    
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
        print("=== 评分维度生成 ===")
        print(f"职位: {job_requirement.position}")
        print(f"必要条件: {job_requirement.must_have}")
        print(f"加分条件: {job_requirement.nice_to_have}")
        print(f"排除条件: {job_requirement.deal_breaker}\n")
        
        result = self.process(job_requirement)
        
        if result["status"] == "success":
            scoring_dimensions = result["scoring_dimensions"]
            print("生成的评分维度:")
            for dim in scoring_dimensions.dimensions:
                print(f"- {dim.name} (权重: {dim.weight:.1%})")
                print(f"  字段: {', '.join(dim.fields)}")
                print(f"  描述: {dim.description}\n")
            
            return scoring_dimensions
        else:
            print(f"生成失败: {result['error']}")
            return result["scoring_dimensions"]


# 使用示例
if __name__ == "__main__":
    # 示例招聘需求
    job_requirement = JobRequirement(
        position="高级后端开发工程师",
        must_have=[
            "5年以上Node.js开发经验",
            "熟练使用PostgreSQL",
            "微服务架构经验",
            "AWS云平台使用经验"
        ],
        nice_to_have=[
            "金融科技行业背景",
            "团队管理经验",
            "高并发系统设计经验"
        ],
        deal_breaker=[
            "少于3年开发经验",
            "无数据库使用经验"
        ]
    )
    
    node = ScoringDimensionNode()
    scoring_dimensions = node.run_standalone(job_requirement)
    print(f"权重验证: {scoring_dimensions.validate_weights()}")