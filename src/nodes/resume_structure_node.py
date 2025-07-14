import asyncio
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from src.models import CandidateProfile, CandidateBasicInfo, Education, WorkExperience, Skill, SkillLevel
from src.utils.resume_parser import ResumeParser
import json
import re
from concurrent.futures import ThreadPoolExecutor
import os

class ResumeStructureNode:
    """简历结构化节点 - 异步批量处理简历并结构化"""
    
    def __init__(self, 
                 model_name: str = "gpt-4o-mini", 
                 temperature: float = 0.3,
                 max_concurrent: int = 5):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.resume_parser = ResumeParser()
        self.max_concurrent = max_concurrent
        self.system_prompt = self._build_system_prompt()
        
    def _build_system_prompt(self) -> str:
        return """你是一个专业的简历结构化分析师，负责将原始简历文本转换为结构化数据。

**你的任务：**
1. 分析简历文本，提取关键信息
2. 将信息组织成标准的结构化格式
3. 推断缺失信息或进行合理估计
4. 确保输出格式一致性

**提取的信息类别：**
1. **基本信息**: 姓名、邮箱、电话、所在地、工作年限、当前职位、当前公司
2. **教育背景**: 学位、专业、学校、毕业年份、绩点
3. **工作经历**: 公司名称、职位、时间范围、工作描述、主要成就
4. **技能信息**: 技能名称、水平等级、使用年限、技能描述
5. **其他信息**: 认证证书、语言能力、项目经验、GitHub/LinkedIn

**输出格式要求：**
输出JSON格式的结构化数据：
```json
{
    "basic_info": {
        "name": "候选人姓名",
        "email": "邮箱地址",
        "phone": "电话号码",
        "location": "所在地",
        "experience_years": 5,
        "current_role": "当前职位",
        "current_company": "当前公司"
    },
    "education": [
        {
            "degree": "学位",
            "major": "专业",
            "school": "学校",
            "graduation_year": 2020,
            "gpa": 3.8
        }
    ],
    "work_experience": [
        {
            "company": "公司名称",
            "position": "职位",
            "start_date": "2020-01",
            "end_date": "2023-12",
            "description": "工作描述",
            "achievements": ["成就1", "成就2"]
        }
    ],
    "skills": [
        {
            "name": "技能名称",
            "level": "intermediate",
            "years_experience": 3,
            "description": "技能描述"
        }
    ],
    "certifications": ["认证1", "认证2"],
    "languages": ["中文", "英文"],
    "projects": ["项目1", "项目2"],
    "github_url": "GitHub链接",
    "linkedin_url": "LinkedIn链接"
}
```

**处理规则：**
1. 如果信息不确定，使用null或空数组
2. 技能水平: beginner/intermediate/advanced/expert
3. 工作年限根据工作经历推算
4. 时间格式统一为YYYY-MM
5. 保持原始信息的准确性，不要添加不存在的信息

**特殊情况处理：**
- 如果简历内容过短或质量差，在basic_info中标注
- 如果是英文简历，保持英文名称
- 如果时间信息不完整，尽量推断
- 如果技能水平不明确，根据工作经验推断"""

    async def process(self, resume_files: List[str]) -> Dict[str, Any]:
        """处理多个简历文件"""
        try:
            # 第一步：解析简历文件
            print(f"开始解析 {len(resume_files)} 个简历文件...")
            parsed_resumes = await self.resume_parser.parse_multiple_resumes(resume_files)
            
            # 过滤成功解析的简历
            valid_resumes = [r for r in parsed_resumes if r["status"] == "success"]
            failed_resumes = [r for r in parsed_resumes if r["status"] == "error"]
            
            print(f"成功解析: {len(valid_resumes)} 个，失败: {len(failed_resumes)} 个")
            
            # 第二步：并发结构化处理
            print("开始结构化处理...")
            structured_results = await self._process_resumes_concurrently(valid_resumes)
            
            # 第三步：创建CandidateProfile对象
            candidate_profiles = []
            for result in structured_results:
                if result["status"] == "success":
                    try:
                        profile = self._create_candidate_profile(result["structured_data"])
                        candidate_profiles.append(profile)
                    except Exception as e:
                        print(f"创建候选人档案失败: {str(e)}")
                        continue
            
            return {
                "status": "success",
                "total_files": len(resume_files),
                "successful_parsed": len(valid_resumes),
                "successful_structured": len(candidate_profiles),
                "failed_files": failed_resumes,
                "candidate_profiles": candidate_profiles
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "candidate_profiles": []
            }
    
    async def _process_resumes_concurrently(self, parsed_resumes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """并发处理简历结构化"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_single_resume(resume_data):
            async with semaphore:
                return await self._structure_single_resume(resume_data)
        
        tasks = [process_single_resume(resume) for resume in parsed_resumes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "error",
                    "error": str(result),
                    "file_path": parsed_resumes[i]["file_path"]
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _structure_single_resume(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """结构化单个简历"""
        try:
            content = resume_data["content"]
            file_name = resume_data["file_name"]
            
            # 清理文本
            clean_content = self.resume_parser.clean_text(content)
            
            # 验证内容质量
            validation = self.resume_parser.validate_resume_content(clean_content)
            if not validation["is_valid"]:
                print(f"简历质量警告 [{file_name}]: {validation['issues']}")
            
            # 构建提示
            prompt = self._build_structure_prompt(clean_content, file_name)
            
            # 调用LLM
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # 解析响应
            structured_data = self._parse_structured_response(response.content)
            
            return {
                "status": "success",
                "file_path": resume_data["file_path"],
                "file_name": file_name,
                "structured_data": structured_data,
                "validation": validation
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "file_path": resume_data["file_path"]
            }
    
    def _build_structure_prompt(self, content: str, file_name: str) -> str:
        """构建结构化提示"""
        return f"""
请分析以下简历内容并提取结构化信息：

**文件名**: {file_name}
**简历内容**:
{content}

请按照要求的JSON格式输出结构化数据。特别注意：
1. 仔细提取基本信息，如姓名、联系方式等
2. 分析工作经历，推断工作年限
3. 识别技能和技术栈
4. 提取教育背景信息
5. 如果信息不确定，请使用null值

请输出JSON格式的结构化数据：
"""
    
    def _parse_structured_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的结构化数据"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # 如果没有```json```标记，尝试寻找JSON结构
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
            
            # 如果都失败，返回默认结构
            return self._get_default_structure()
            
        except json.JSONDecodeError:
            return self._get_default_structure()
    
    def _get_default_structure(self) -> Dict[str, Any]:
        """获取默认结构"""
        return {
            "basic_info": {
                "name": "未知候选人",
                "email": None,
                "phone": None,
                "location": None,
                "experience_years": None,
                "current_role": None,
                "current_company": None
            },
            "education": [],
            "work_experience": [],
            "skills": [],
            "certifications": [],
            "languages": [],
            "projects": [],
            "github_url": None,
            "linkedin_url": None
        }
    
    def _create_candidate_profile(self, structured_data: Dict[str, Any]) -> CandidateProfile:
        """创建候选人档案对象"""
        # 基本信息
        basic_info_data = structured_data.get("basic_info", {})
        basic_info = CandidateBasicInfo(
            name=basic_info_data.get("name", "未知候选人"),
            email=basic_info_data.get("email"),
            phone=basic_info_data.get("phone"),
            location=basic_info_data.get("location"),
            experience_years=basic_info_data.get("experience_years"),
            current_role=basic_info_data.get("current_role"),
            current_company=basic_info_data.get("current_company")
        )
        
        # 教育背景
        education_list = []
        for edu_data in structured_data.get("education", []):
            education = Education(
                degree=edu_data.get("degree", ""),
                major=edu_data.get("major", ""),
                school=edu_data.get("school", ""),
                graduation_year=edu_data.get("graduation_year"),
                gpa=edu_data.get("gpa")
            )
            education_list.append(education)
        
        # 工作经历
        work_experience_list = []
        for work_data in structured_data.get("work_experience", []):
            work_exp = WorkExperience(
                company=work_data.get("company", ""),
                position=work_data.get("position", ""),
                start_date=work_data.get("start_date"),
                end_date=work_data.get("end_date"),
                description=work_data.get("description"),
                achievements=work_data.get("achievements", [])
            )
            work_experience_list.append(work_exp)
        
        # 技能
        skills_list = []
        for skill_data in structured_data.get("skills", []):
            skill_level = skill_data.get("level")
            if skill_level and skill_level in [e.value for e in SkillLevel]:
                skill_level_enum = SkillLevel(skill_level)
            else:
                skill_level_enum = None
            
            skill = Skill(
                name=skill_data.get("name", ""),
                level=skill_level_enum,
                years_experience=skill_data.get("years_experience"),
                description=skill_data.get("description")
            )
            skills_list.append(skill)
        
        # 创建候选人档案
        profile = CandidateProfile(
            basic_info=basic_info,
            education=education_list,
            work_experience=work_experience_list,
            skills=skills_list,
            certifications=structured_data.get("certifications", []),
            languages=structured_data.get("languages", []),
            projects=structured_data.get("projects", []),
            github_url=structured_data.get("github_url"),
            linkedin_url=structured_data.get("linkedin_url")
        )
        
        return profile
    
    async def run_standalone(self, resume_files: List[str]) -> List[CandidateProfile]:
        """独立运行模式"""
        print("=== 简历结构化处理 ===")
        print(f"待处理简历数量: {len(resume_files)}")
        
        # 验证文件存在性
        existing_files = []
        for file_path in resume_files:
            if os.path.exists(file_path):
                existing_files.append(file_path)
            else:
                print(f"文件不存在: {file_path}")
        
        if not existing_files:
            print("没有有效的简历文件")
            return []
        
        result = await self.process(existing_files)
        
        if result["status"] == "success":
            print(f"\\n=== 处理结果 ===")
            print(f"总文件数: {result['total_files']}")
            print(f"成功解析: {result['successful_parsed']}")
            print(f"成功结构化: {result['successful_structured']}")
            
            if result["failed_files"]:
                print(f"\\n失败文件:")
                for failed in result["failed_files"]:
                    print(f"- {failed['file_path']}: {failed['error']}")
            
            print(f"\\n=== 候选人信息 ===")
            for i, profile in enumerate(result["candidate_profiles"], 1):
                print(f"{i}. {profile.basic_info.name}")
                print(f"   经验: {profile.basic_info.experience_years or '未知'} 年")
                print(f"   技能: {len(profile.skills)} 项")
                print(f"   工作经历: {len(profile.work_experience)} 份")
                print()
            
            return result["candidate_profiles"]
        else:
            print(f"处理失败: {result['error']}")
            return []


# 使用示例
async def main():
    # 示例简历文件
    resume_files = [
        "examples/resume1.pdf",
        "examples/resume2.docx",
        "examples/resume3.txt"
    ]
    
    node = ResumeStructureNode()
    profiles = await node.run_standalone(resume_files)
    
    print(f"\\n成功处理 {len(profiles)} 个候选人档案")

if __name__ == "__main__":
    asyncio.run(main())