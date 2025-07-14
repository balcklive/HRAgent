from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import uuid
from datetime import datetime

class SkillLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class RequirementType(str, Enum):
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"
    DEAL_BREAKER = "deal_breaker"

class EvaluationStatus(str, Enum):
    PASS = "✓"
    WARNING = "⚠️"
    FAIL = "❌"

class JobRequirement(BaseModel):
    """招聘需求数据模型"""
    position: str = Field(..., description="职位名称")
    must_have: List[str] = Field(default_factory=list, description="必要条件")
    nice_to_have: List[str] = Field(default_factory=list, description="加分条件")
    deal_breaker: List[str] = Field(default_factory=list, description="排除条件")
    min_years_experience: Optional[int] = Field(None, description="最低工作年限")
    preferred_education: Optional[str] = Field(None, description="教育背景要求")
    industry: Optional[str] = Field(None, description="所属行业")
    
    class Config:
        use_enum_values = True

class ScoringDimension(BaseModel):
    """评分维度配置"""
    name: str = Field(..., description="维度名称")
    weight: float = Field(..., description="权重 (0-1之间)")
    fields: List[str] = Field(..., description="评分字段列表")
    description: Optional[str] = Field(None, description="维度描述")

class ScoringDimensions(BaseModel):
    """完整评分维度配置"""
    dimensions: List[ScoringDimension] = Field(..., description="评分维度列表")
    total_weight: float = Field(1.0, description="总权重")
    
    def validate_weights(self) -> bool:
        """验证权重总和是否为1.0"""
        return abs(sum(d.weight for d in self.dimensions) - 1.0) < 0.01

class CandidateBasicInfo(BaseModel):
    """候选人基本信息"""
    name: str = Field(..., description="姓名")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="电话")
    location: Optional[str] = Field(None, description="所在地")
    experience_years: Optional[int] = Field(None, description="工作年限")
    current_role: Optional[str] = Field(None, description="当前职位")
    current_company: Optional[str] = Field(None, description="当前公司")

class Education(BaseModel):
    """教育背景"""
    degree: str = Field(..., description="学位")
    major: str = Field(..., description="专业")
    school: str = Field(..., description="学校")
    graduation_year: Optional[int] = Field(None, description="毕业年份")
    gpa: Optional[float] = Field(None, description="绩点")

class WorkExperience(BaseModel):
    """工作经历"""
    company: str = Field(..., description="公司名称")
    position: str = Field(..., description="职位")
    start_date: Optional[str] = Field(None, description="开始时间")
    end_date: Optional[str] = Field(None, description="结束时间")
    description: Optional[str] = Field(None, description="工作描述")
    achievements: List[str] = Field(default_factory=list, description="主要成就")

class Skill(BaseModel):
    """技能信息"""
    name: str = Field(..., description="技能名称")
    level: Optional[SkillLevel] = Field(None, description="技能水平")
    years_experience: Optional[int] = Field(None, description="使用年限")
    description: Optional[str] = Field(None, description="技能描述")

class CandidateProfile(BaseModel):
    """候选人完整档案"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="候选人ID")
    basic_info: CandidateBasicInfo = Field(..., description="基本信息")
    education: List[Education] = Field(default_factory=list, description="教育背景")
    work_experience: List[WorkExperience] = Field(default_factory=list, description="工作经历")
    skills: List[Skill] = Field(default_factory=list, description="技能列表")
    certifications: List[str] = Field(default_factory=list, description="认证证书")
    languages: List[str] = Field(default_factory=list, description="语言能力")
    projects: List[str] = Field(default_factory=list, description="项目经验")
    github_url: Optional[str] = Field(None, description="GitHub链接")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn链接")
    
    class Config:
        use_enum_values = True

class DimensionScore(BaseModel):
    """维度评分"""
    dimension_name: str = Field(..., description="维度名称")
    score: float = Field(..., ge=0, le=10, description="分数 (0-10)")
    status: EvaluationStatus = Field(..., description="评估状态")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细评分信息")
    comments: Optional[str] = Field(None, description="评分说明")

class CandidateEvaluation(BaseModel):
    """候选人评价结果"""
    candidate_id: str = Field(..., description="候选人ID")
    candidate_name: str = Field(..., description="候选人姓名")
    dimension_scores: List[DimensionScore] = Field(..., description="各维度评分")
    overall_score: float = Field(..., ge=0, le=10, description="总分")
    recommendation: str = Field(..., description="推荐建议")
    strengths: List[str] = Field(default_factory=list, description="优势")
    weaknesses: List[str] = Field(default_factory=list, description="劣势")
    ranking: Optional[int] = Field(None, description="排名")
    
    class Config:
        use_enum_values = True

class WorkflowState(BaseModel):
    """工作流状态"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="会话ID")
    jd_text: Optional[str] = Field(None, description="JD原文")
    resume_files: List[str] = Field(default_factory=list, description="简历文件路径")
    job_requirement: Optional[JobRequirement] = Field(None, description="招聘需求")
    scoring_dimensions: Optional[ScoringDimensions] = Field(None, description="评分维度")
    candidate_profiles: List[CandidateProfile] = Field(default_factory=list, description="候选人档案")
    evaluations: List[CandidateEvaluation] = Field(default_factory=list, description="评价结果")
    final_report: Optional[str] = Field(None, description="最终报告")
    current_step: str = Field("start", description="当前步骤")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    
    class Config:
        use_enum_values = True

class InteractionMessage(BaseModel):
    """交互消息"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")

class RequirementConfirmationState(BaseModel):
    """需求确认状态"""
    jd_text: str = Field(..., description="JD原文")
    position: Optional[str] = Field(None, description="职位名称")
    must_have: List[str] = Field(default_factory=list, description="必要条件")
    nice_to_have: List[str] = Field(default_factory=list, description="加分条件")
    deal_breaker: List[str] = Field(default_factory=list, description="排除条件")
    conversation_history: List[InteractionMessage] = Field(default_factory=list, description="对话历史")
    is_complete: bool = Field(False, description="是否完成确认")
    missing_info: List[str] = Field(default_factory=list, description="缺失信息")
    
    def to_job_requirement(self) -> JobRequirement:
        """转换为JobRequirement"""
        return JobRequirement(
            position=self.position or "未知职位",
            must_have=self.must_have,
            nice_to_have=self.nice_to_have,
            deal_breaker=self.deal_breaker
        )