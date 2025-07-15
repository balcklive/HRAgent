# Author: Peng Fei

import asyncio
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from src.models import CandidateProfile, CandidateBasicInfo, Education, WorkExperience, Skill
from src.prompts import (
    RESUME_STRUCTURE_SYSTEM_PROMPT,
    RESUME_STRUCTURE_PROMPT_TEMPLATE
)
from src.utils.resume_parser import ResumeParser
import json
import re
from concurrent.futures import ThreadPoolExecutor

class ResumeStructureNode:
    """简历结构化节点 - 将简历文本转换为结构化数据"""
    
    def __init__(self, 
                 model_name: str = "gpt-4o-mini", 
                 temperature: float = 0.3,
                 max_concurrent: int = 5):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.max_concurrent = max_concurrent
        self.system_prompt = RESUME_STRUCTURE_SYSTEM_PROMPT
        self.resume_parser = ResumeParser()
        
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
        return RESUME_STRUCTURE_PROMPT_TEMPLATE.format(
            file_name=file_name,
            content=content
        )
    
    def _parse_structured_response(self, response: str) -> Dict[str, Any]:
        """解析结构化响应"""
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
            
            # 如果都失败，返回默认结构
            return self._get_default_structure()
            
        except json.JSONDecodeError:
            return self._get_default_structure()
    
    def _get_default_structure(self) -> Dict[str, Any]:
        """获取默认结构化数据"""
        return {
            "basic_info": {
                "name": "未知",
                "email": None,
                "phone": None,
                "location": None,
                "experience_years": 0,
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
            name=basic_info_data.get("name", "未知"),
            email=basic_info_data.get("email"),
            phone=basic_info_data.get("phone"),
            location=basic_info_data.get("location"),
            experience_years=basic_info_data.get("experience_years", 0),
            current_role=basic_info_data.get("current_role"),
            current_company=basic_info_data.get("current_company")
        )
        
        # 教育背景
        education_list = []
        for edu_data in structured_data.get("education", []):
            education = Education(
                degree=edu_data.get("degree"),
                major=edu_data.get("major"),
                school=edu_data.get("school"),
                graduation_year=edu_data.get("graduation_year"),
                gpa=edu_data.get("gpa")
            )
            education_list.append(education)
        
        # 工作经历
        work_experience_list = []
        for work_data in structured_data.get("work_experience", []):
            work_exp = WorkExperience(
                company=work_data.get("company"),
                position=work_data.get("position"),
                start_date=work_data.get("start_date"),
                end_date=work_data.get("end_date"),
                description=work_data.get("description"),
                achievements=work_data.get("achievements", [])
            )
            work_experience_list.append(work_exp)
        
        # 技能信息
        skills_list = []
        for skill_data in structured_data.get("skills", []):
            skill = Skill(
                name=skill_data.get("name"),
                level=skill_data.get("level"),
                years_experience=skill_data.get("years_experience"),
                description=skill_data.get("description")
            )
            skills_list.append(skill)
        
        # 其他信息
        certifications = structured_data.get("certifications", [])
        languages = structured_data.get("languages", [])
        projects = structured_data.get("projects", [])
        github_url = structured_data.get("github_url")
        linkedin_url = structured_data.get("linkedin_url")
        
        return CandidateProfile(
            id=f"candidate_{len(work_experience_list)}_{len(skills_list)}",  # 简单ID生成
            basic_info=basic_info,
            education=education_list,
            work_experience=work_experience_list,
            skills=skills_list,
            certifications=certifications,
            languages=languages,
            projects=projects,
            github_url=github_url,
            linkedin_url=linkedin_url
        )
    
    async def run_standalone(self, resume_files: List[str]) -> List[CandidateProfile]:
        """独立运行模式"""
        result = await self.process(resume_files)
        
        if result["status"] == "success":
            print(f"简历结构化完成: {result['successful_structured']}/{result['total_files']} 个文件")
            return result["candidate_profiles"]
        else:
            print(f"简历结构化失败: {result['error']}")
            return []

async def main():
    """测试函数"""
    # 示例简历文件路径
    resume_files = [
        "path/to/resume1.pdf",
        "path/to/resume2.docx"
    ]
    
    node = ResumeStructureNode()
    candidate_profiles = await node.run_standalone(resume_files)
    
    for profile in candidate_profiles:
        print(f"候选人: {profile.basic_info.name}")
        print(f"职位: {profile.basic_info.current_role}")
        print(f"公司: {profile.basic_info.current_company}")
        print(f"经验: {profile.basic_info.experience_years}年")
        print("---")

if __name__ == "__main__":
    asyncio.run(main())