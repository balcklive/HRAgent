# Author: Peng Fei

import asyncio
from typing import List, Dict, Any, Optional, Callable
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
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

class ResumeStructureNode:
    """简历结构化节点 - 将简历文本转换为结构化数据"""
    
    def __init__(self, 
                 model_name: str = "gpt-4o-mini", 
                 temperature: float = 0.3,
                 max_concurrent: int = 5,
                 save_structured_results: bool = True):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.max_concurrent = max_concurrent
        self.system_prompt = RESUME_STRUCTURE_SYSTEM_PROMPT
        self.resume_parser = ResumeParser()
        self.save_structured_results = save_structured_results
        
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
            
            # 第三步：保存结构化结果（如果启用）
            if self.save_structured_results:
                await self._save_structured_results_to_disk(structured_results)
            
            # 第四步：创建CandidateProfile对象
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

    async def process_stream(self, resume_files: List[str], progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """处理简历文件（带进度流式输出）"""
        if progress_callback:
            await progress_callback({
                "stage": "resume_processing",
                "message": "Start parsing resume files",
                "progress": 15,
                "total_items": len(resume_files),
                "completed_items": 0
            })
        
        # 解析简历文件
        parsed_resumes = await self._parse_resumes_with_progress(resume_files, progress_callback)
        
        if progress_callback:
            await progress_callback({
                "stage": "resume_processing",
                "message": "Start structuring resume content",
                "progress": 25,
                "total_items": len(parsed_resumes),
                "completed_items": 0
            })
        
        # 结构化简历
        structured_results = await self._process_resumes_concurrently_stream(parsed_resumes, progress_callback)
        
        if progress_callback:
            await progress_callback({
                "stage": "resume_processing",
                "message": "Saving structured results",
                "progress": 35,
                "total_items": len(structured_results),
                "completed_items": len(structured_results)
            })
        
        # 保存结果
        if self.save_structured_results:
            await self._save_structured_results_to_disk(structured_results)
        
        # 创建CandidateProfile对象
        candidate_profiles = []
        for result in structured_results:
            if result["status"] == "success":
                try:
                    profile = self._create_candidate_profile(result["structured_data"])
                    candidate_profiles.append(profile)
                except Exception as e:
                    print(f"创建候选人档案失败: {str(e)}")
                    continue
        
        if progress_callback:
            await progress_callback({
                "stage": "resume_processing",
                "message": "Resume processing completed",
                "progress": 40,
                "total_items": len(resume_files),
                "completed_items": len(resume_files)
            })
        
        return {
            "status": "success",
            "total_files": len(resume_files),
            "successful_parsed": len(parsed_resumes),
            "successful_structured": len(candidate_profiles),
            "failed_files": [r for r in parsed_resumes if r["status"] == "error"],
            "candidate_profiles": candidate_profiles
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
    
    async def _save_structured_results_to_disk(self, structured_results: List[Dict[str, Any]]) -> None:
        """保存结构化结果到硬盘"""
        try:
            # 创建保存目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dir = f"structured_resumes_{timestamp}"
            os.makedirs(save_dir, exist_ok=True)
            
            print(f"💾 正在保存结构化结果到目录: {save_dir}")
            
            # 保存每个候选人的结构化结果
            for i, result in enumerate(structured_results):
                if result["status"] == "success":
                    # 从文件路径获取候选人名称
                    file_name = result.get("file_name", f"candidate_{i+1}")
                    candidate_name = os.path.splitext(file_name)[0]
                    
                    # 准备保存的数据
                    save_data = {
                        "file_info": {
                            "original_file": result["file_path"],
                            "file_name": result["file_name"],
                            "processing_time": datetime.now().isoformat(),
                            "validation": result.get("validation", {})
                        },
                        "structured_data": result["structured_data"]
                    }
                    
                    # 保存为JSON文件
                    json_file = os.path.join(save_dir, f"{candidate_name}_structured.json")
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(save_data, f, ensure_ascii=False, indent=2)
                    
                    # 保存为可读的Markdown文件
                    md_file = os.path.join(save_dir, f"{candidate_name}_structured.md")
                    await self._save_as_markdown(save_data, md_file)
                    
                    # 从结构化数据中提取候选人姓名
                    candidate_real_name = save_data["structured_data"].get("basic_info", {}).get("name", candidate_name)
                    print(f"✅ 已保存候选人 '{candidate_real_name}' 的结构化结果")
                    
                elif result["status"] == "error":
                    # 保存错误信息
                    error_file = os.path.join(save_dir, f"error_{i+1}.json")
                    with open(error_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    print(f"❌ 已保存错误信息: {result.get('file_path', 'unknown')}")
            
            # 创建汇总文件
            summary_file = os.path.join(save_dir, "summary.json")
            summary_data = {
                "processing_time": datetime.now().isoformat(),
                "total_files": len(structured_results),
                "successful_files": len([r for r in structured_results if r["status"] == "success"]),
                "failed_files": len([r for r in structured_results if r["status"] == "error"]),
                "results": [
                    {
                        "file_name": r.get("file_name", "unknown"),
                        "file_path": r.get("file_path", "unknown"),
                        "status": r["status"],
                        "candidate_name": r.get("structured_data", {}).get("basic_info", {}).get("name", "unknown") if r["status"] == "success" else None,
                        "error": r.get("error") if r["status"] == "error" else None
                    } for r in structured_results
                ]
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            
            print(f"📄 已创建汇总文件: {summary_file}")
            print(f"📁 结构化结果已保存到目录: {save_dir}")
            
        except Exception as e:
            print(f"❌ 保存结构化结果失败: {str(e)}")
    
    async def _save_as_markdown(self, save_data: Dict[str, Any], md_file: str) -> None:
        """将结构化数据保存为Markdown格式"""
        try:
            structured_data = save_data["structured_data"]
            file_info = save_data["file_info"]
            
            md_content = []
            
            # 标题
            candidate_name = structured_data.get("basic_info", {}).get("name", "未知候选人")
            md_content.append(f"# {candidate_name} - 简历结构化结果\n")
            
            # 文件信息
            md_content.append("## 文件信息\n")
            md_content.append(f"- **原始文件**: {file_info['original_file']}")
            md_content.append(f"- **处理时间**: {file_info['processing_time']}")
            md_content.append(f"- **验证状态**: {'✅ 通过' if file_info.get('validation', {}).get('is_valid', False) else '⚠️ 存在问题'}")
            if not file_info.get('validation', {}).get('is_valid', False):
                issues = file_info.get('validation', {}).get('issues', [])
                if issues:
                    md_content.append(f"- **问题**: {', '.join(issues)}")
            md_content.append("")
            
            # 基本信息
            basic_info = structured_data.get("basic_info", {})
            md_content.append("## 基本信息\n")
            md_content.append(f"- **姓名**: {basic_info.get('name', '未知')}")
            md_content.append(f"- **邮箱**: {basic_info.get('email', '未提供')}")
            md_content.append(f"- **电话**: {basic_info.get('phone', '未提供')}")
            md_content.append(f"- **所在地**: {basic_info.get('location', '未提供')}")
            md_content.append(f"- **工作经验**: {basic_info.get('experience_years', 0)} 年")
            md_content.append(f"- **当前职位**: {basic_info.get('current_role', '未提供')}")
            md_content.append(f"- **当前公司**: {basic_info.get('current_company', '未提供')}")
            md_content.append("")
            
            # 教育背景
            education = structured_data.get("education", [])
            md_content.append("## 教育背景\n")
            if education:
                for edu in education:
                    md_content.append(f"- **{edu.get('degree', '未知学位')}** - {edu.get('major', '未知专业')}")
                    md_content.append(f"  - 学校: {edu.get('school', '未知')}")
                    md_content.append(f"  - 毕业年份: {edu.get('graduation_year', '未知')}")
                    if edu.get('gpa'):
                        md_content.append(f"  - GPA: {edu.get('gpa')}")
            else:
                md_content.append("- 无教育背景信息")
            md_content.append("")
            
            # 工作经历
            work_experience = structured_data.get("work_experience", [])
            md_content.append("## 工作经历\n")
            if work_experience:
                for work in work_experience:
                    md_content.append(f"### {work.get('position', '未知职位')} - {work.get('company', '未知公司')}")
                    md_content.append(f"- **时间**: {work.get('start_date', '未知')} 至 {work.get('end_date', '未知')}")
                    if work.get('description'):
                        md_content.append(f"- **描述**: {work.get('description')}")
                    achievements = work.get('achievements', [])
                    if achievements:
                        md_content.append("- **主要成就**:")
                        for achievement in achievements:
                            md_content.append(f"  - {achievement}")
                    md_content.append("")
            else:
                md_content.append("- 无工作经历信息\n")
            
            # 技能信息
            skills = structured_data.get("skills", [])
            md_content.append("## 技能信息\n")
            if skills:
                for skill in skills:
                    skill_info = f"- **{skill.get('name', '未知技能')}"
                    if skill.get('level'):
                        skill_info += f"** ({skill.get('level')})"
                    else:
                        skill_info += "**"
                    if skill.get('years_experience'):
                        skill_info += f" - {skill.get('years_experience')} 年经验"
                    md_content.append(skill_info)
                    if skill.get('description'):
                        md_content.append(f"  - {skill.get('description')}")
            else:
                md_content.append("- 无技能信息")
            md_content.append("")
            
            # 其他信息
            certifications = structured_data.get("certifications", [])
            if certifications:
                md_content.append("## 认证证书\n")
                for cert in certifications:
                    md_content.append(f"- {cert}")
                md_content.append("")
            
            languages = structured_data.get("languages", [])
            if languages:
                md_content.append("## 语言能力\n")
                for lang in languages:
                    md_content.append(f"- {lang}")
                md_content.append("")
            
            projects = structured_data.get("projects", [])
            if projects:
                md_content.append("## 项目经验\n")
                for project in projects:
                    md_content.append(f"- {project}")
                md_content.append("")
            
            # 链接信息
            links = []
            if structured_data.get("github_url"):
                links.append(f"- **GitHub**: {structured_data.get('github_url')}")
            if structured_data.get("linkedin_url"):
                links.append(f"- **LinkedIn**: {structured_data.get('linkedin_url')}")
            
            if links:
                md_content.append("## 链接信息\n")
                md_content.extend(links)
                md_content.append("")
            
            # 写入文件
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(md_content))
                
        except Exception as e:
            print(f"❌ 保存Markdown文件失败: {str(e)}")
    
    async def _structure_single_resume(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """结构化单个简历"""
        try:
            # 检查是否有content字段
            if "content" not in resume_data:
                return {
                    "status": "error",
                    "error": "缺少简历内容",
                    "file_path": resume_data.get("file_path", "unknown")
                }
            
            content = resume_data["content"]
            file_name = resume_data.get("file_name", "unknown")
            
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

    async def _parse_resumes_with_progress(self, resume_files: List[str], progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """解析简历文件（带进度）"""
        parsed_resumes = []
        
        for i, file_path in enumerate(resume_files):
            if progress_callback:
                await progress_callback({
                    "stage": "resume_processing",
                    "message": f"Parsing resume file: {os.path.basename(file_path)}",
                    "progress": 15 + (i / len(resume_files)) * 10,
                    "current_item": os.path.basename(file_path),
                    "total_items": len(resume_files),
                    "completed_items": i
                })
            
            try:
                parsed_resume = await self._parse_single_resume(file_path)
                parsed_resumes.append(parsed_resume)
            except Exception as e:
                print(f"❌ 解析简历失败 {file_path}: {str(e)}")
                parsed_resumes.append({
                    "status": "error",
                    "error": str(e),
                    "file_path": file_path
                })
        
        return parsed_resumes

    async def _parse_single_resume(self, file_path: str) -> Dict[str, Any]:
        """解析单个简历文件"""
        try:
            # 解析简历文件
            parse_result = await self.resume_parser.parse_resume_file(file_path)
            
            if parse_result["status"] == "error":
                raise ValueError(parse_result["error"])
            
            content = parse_result["content"]
            
            if not content or content.strip() == "":
                raise ValueError("文件内容为空")
            
            return {
                "status": "success",
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "content": content
            }
        except Exception as e:
            print(f"❌ 解析单个简历失败 {file_path}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path
            }

    async def _process_resumes_concurrently_stream(self, parsed_resumes: List[Dict[str, Any]], progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """并发处理简历结构化（带进度）"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        completed_count = 0
        
        async def process_single_resume_stream(resume_data):
            nonlocal completed_count
            async with semaphore:
                result = await self._structure_single_resume(resume_data)
                completed_count += 1
                
                if progress_callback:
                    await progress_callback({
                        "stage": "resume_processing",
                        "message": f"Completed resume structuring: {os.path.basename(resume_data.get('file_path', 'unknown'))}",
                        "progress": 25 + (completed_count / len(parsed_resumes)) * 10,
                        "current_item": os.path.basename(resume_data.get('file_path', 'unknown')),
                        "total_items": len(parsed_resumes),
                        "completed_items": completed_count
                    })
                
                return result
        
        tasks = [process_single_resume_stream(resume) for resume in parsed_resumes]
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