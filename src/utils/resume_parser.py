import os
import asyncio
import aiofiles
from typing import List, Dict, Any, Optional
import PyPDF2
import docx2txt
from docx import Document
import re
from pathlib import Path

class ResumeParser:
    """简历解析器 - 支持多种格式的简历文件解析"""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt']
    
    async def parse_resume_file(self, file_path: str) -> Dict[str, Any]:
        """解析单个简历文件"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                return {
                    "status": "error",
                    "error": f"文件不存在: {file_path}",
                    "content": ""
                }
            
            file_extension = file_path.suffix.lower()
            
            if file_extension not in self.supported_formats:
                return {
                    "status": "error",
                    "error": f"不支持的文件格式: {file_extension}",
                    "content": ""
                }
            
            # 根据文件类型解析
            if file_extension == '.pdf':
                content = await self._parse_pdf(file_path)
            elif file_extension in ['.docx', '.doc']:
                content = await self._parse_docx(file_path)
            elif file_extension == '.txt':
                content = await self._parse_txt(file_path)
            else:
                content = ""
            
            return {
                "status": "success",
                "file_path": str(file_path),
                "file_name": file_path.name,
                "content": content,
                "file_size": file_path.stat().st_size
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "file_path": str(file_path),
                "content": ""
            }
    
    async def _parse_pdf(self, file_path: Path) -> str:
        """解析PDF文件"""
        try:
            content = ""
            async with aiofiles.open(file_path, 'rb') as file:
                file_content = await file.read()
                
            # 使用PyPDF2解析PDF
            import io
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            
            for page in pdf_reader.pages:
                content += page.extract_text() + "\n"
            
            return content.strip()
            
        except Exception as e:
            # 如果PyPDF2失败，尝试使用pdfplumber
            try:
                import pdfplumber
                async with aiofiles.open(file_path, 'rb') as file:
                    file_content = await file.read()
                
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    content = ""
                    for page in pdf.pages:
                        content += page.extract_text() + "\n"
                
                return content.strip()
                
            except Exception as e2:
                raise Exception(f"PDF解析失败: {str(e2)}")
    
    async def _parse_docx(self, file_path: Path) -> str:
        """解析Word文档"""
        try:
            # 尝试使用docx2txt
            content = docx2txt.process(str(file_path))
            if content.strip():
                return content.strip()
            
            # 如果docx2txt失败，尝试使用python-docx
            doc = Document(str(file_path))
            content = ""
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
            
            return content.strip()
            
        except Exception as e:
            raise Exception(f"Word文档解析失败: {str(e)}")
    
    async def _parse_txt(self, file_path: Path) -> str:
        """解析文本文件"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
                return content.strip()
                
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                async with aiofiles.open(file_path, 'r', encoding='gbk') as file:
                    content = await file.read()
                    return content.strip()
            except Exception as e:
                raise Exception(f"文本文件解析失败: {str(e)}")
    
    async def parse_multiple_resumes(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """批量解析多个简历文件"""
        tasks = []
        for file_path in file_paths:
            task = self.parse_resume_file(file_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "error",
                    "error": str(result),
                    "file_path": file_paths[i],
                    "content": ""
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def clean_text(self, text: str) -> str:
        """清理文本内容"""
        if not text:
            return ""
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符
        text = re.sub(r'[^\w\s\u4e00-\u9fff.,;:!?@#$%^&*()_+\-=\[\]{}"\'\\|<>~`]', '', text)
        
        # 标准化行尾
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        return text.strip()
    
    def validate_resume_content(self, content: str) -> Dict[str, Any]:
        """验证简历内容质量"""
        if not content or len(content.strip()) < 50:
            return {
                "is_valid": False,
                "issues": ["简历内容过短或为空"]
            }
        
        issues = []
        
        # 检查是否包含基本信息
        if not re.search(r'[\u4e00-\u9fff]{2,4}', content):  # 中文姓名
            if not re.search(r'[A-Za-z]+ [A-Za-z]+', content):  # 英文姓名
                issues.append("未找到姓名信息")
        
        # 检查是否包含联系方式
        if not re.search(r'[\d\-\+\(\)\s]{10,}', content):  # 电话
            if not re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content):  # 邮箱
                issues.append("未找到联系方式")
        
        # 检查是否包含工作经验或技能
        work_keywords = ['工作经验', '工作经历', '职业经历', 'experience', 'work', '公司', 'company']
        skill_keywords = ['技能', 'skill', '技术', 'technology', '熟练', 'proficient']
        
        has_work = any(keyword in content.lower() for keyword in work_keywords)
        has_skill = any(keyword in content.lower() for keyword in skill_keywords)
        
        if not has_work and not has_skill:
            issues.append("未找到工作经验或技能信息")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "content_length": len(content),
            "has_chinese": bool(re.search(r'[\u4e00-\u9fff]', content)),
            "has_english": bool(re.search(r'[A-Za-z]', content))
        }


# 使用示例
async def main():
    parser = ResumeParser()
    
    # 测试单个文件解析
    # result = await parser.parse_resume_file("path/to/resume.pdf")
    # print(f"解析结果: {result}")
    
    # 测试批量解析
    file_paths = [
        "resumes/resume1.pdf",
        "resumes/resume2.docx",
        "resumes/resume3.txt"
    ]
    
    # results = await parser.parse_multiple_resumes(file_paths)
    # for result in results:
    #     if result["status"] == "success":
    #         validation = parser.validate_resume_content(result["content"])
    #         print(f"文件: {result['file_name']}")
    #         print(f"内容长度: {len(result['content'])}")
    #         print(f"验证结果: {validation}")
    #         print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())