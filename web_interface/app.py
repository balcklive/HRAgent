#!/usr/bin/env python3
"""
HR智能体Web界面 - FastAPI应用
"""
import os
import sys
import asyncio
import uuid
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import json

from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflow_optimized import OptimizedHRAgentWorkflow
from src.models import JobRequirement, WorkflowState
from src.nodes import RequirementConfirmationNode
from src.models import RequirementConfirmationState

app = FastAPI(
    title="HR智能体简历筛选系统",
    description="基于AI的智能简历筛选和评估系统",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件和模板
app.mount("/static", StaticFiles(directory="web_interface/static"), name="static")
templates = Jinja2Templates(directory="web_interface/templates")

# 工作流实例
workflow = OptimizedHRAgentWorkflow()

# 任务状态存储
task_status = {}

# 聊天会话存储
chat_sessions = {}

# 需求确认节点
requirement_node = RequirementConfirmationNode()

def serialize_workflow_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """序列化工作流结果，避免JSON序列化错误"""
    # 序列化复杂对象以避免JSON序列化错误
    evaluations = result.get("evaluations", [])
    if evaluations:
        # 如果evaluations是对象列表，转换为字典列表
        if hasattr(evaluations[0], 'model_dump'):
            evaluations = [eval.model_dump() for eval in evaluations]
        elif hasattr(evaluations[0], 'dict'):
            evaluations = [eval.dict() for eval in evaluations]
    
    job_requirement = result.get("job_requirement", {})
    if hasattr(job_requirement, 'model_dump'):
        job_requirement = job_requirement.model_dump()
    elif hasattr(job_requirement, 'dict'):
        job_requirement = job_requirement.dict()
    
    scoring_dimensions = result.get("scoring_dimensions", {})
    if hasattr(scoring_dimensions, 'model_dump'):
        scoring_dimensions = scoring_dimensions.model_dump()
    elif hasattr(scoring_dimensions, 'dict'):
        scoring_dimensions = scoring_dimensions.dict()
    
    return {
        "report": result.get("final_report", ""),  # 统一使用report字段
        "report_file": result.get("report_file", ""),
        "evaluations": evaluations,
        "job_requirement": job_requirement,
        "scoring_dimensions": scoring_dimensions,
        "total_duration": result.get("total_duration", 0)
    }

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页面"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    jd_text: str = Form(...),
    resume_files: List[UploadFile] = File(...)
):
    """处理文件上传和JD文本"""
    try:
        # 验证输入
        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="JD文本不能为空")
        
        if not resume_files:
            raise HTTPException(status_code=400, detail="请至少上传一个简历文件")
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "开始处理...",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat()
        }
        
        # 保存上传的文件
        upload_dir = Path("web_interface/static/uploads") / task_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        for file in resume_files:
            if file.filename:
                file_path = upload_dir / file.filename
                content = await file.read()
                
                # 保存文件
                with open(file_path, "wb") as f:
                    f.write(content)
                
                saved_files.append(str(file_path))
        
        # 在后台处理任务
        background_tasks.add_task(
            process_evaluation_task,
            task_id,
            jd_text,
            saved_files
        )
        
        return JSONResponse({
            "task_id": task_id,
            "message": "文件上传成功，开始处理",
            "files_count": len(saved_files)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_evaluation_task(task_id: str, jd_text: str, resume_files: List[str]):
    """后台处理评估任务"""
    try:
        # 更新状态
        task_status[task_id]["progress"] = 10
        task_status[task_id]["message"] = "正在处理JD和简历文件..."
        
        # 对于传统上传方式，使用自动需求确认
        # 这里直接调用原始的工作流方法，让它自动提取需求
        result = await workflow.run_optimized_workflow(jd_text, resume_files)
        
        # 更新状态
        task_status[task_id]["progress"] = 100
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["message"] = "处理完成"
        # 使用序列化函数避免JSON序列化错误
        task_status[task_id]["result"] = serialize_workflow_result(result)
        
        # 清理上传的文件
        try:
            upload_dir = Path("web_interface/static/uploads") / task_id
            if upload_dir.exists():
                import shutil
                shutil.rmtree(upload_dir)
        except:
            pass
            
    except Exception as e:
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["error"] = str(e)
        task_status[task_id]["message"] = f"处理失败: {str(e)}"

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return JSONResponse(task_status[task_id])

@app.get("/result/{task_id}")
async def get_result(request: Request, task_id: str):
    """获取处理结果页面"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = task_status[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = task["result"]
    
    # 准备模板数据
    template_data = {
        "request": request,
        "task_id": task_id,
        "result": result,
        "created_at": task["created_at"]
    }
    
    return templates.TemplateResponse("result.html", template_data)

@app.get("/download/{task_id}")
async def download_report(task_id: str):
    """下载评估报告"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = task_status[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    # 返回报告文件内容
    result = task["result"]
    report_content = result.get("report", "")
    
    from fastapi.responses import Response
    
    return Response(
        content=report_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=evaluation_report_{task_id}.md"}
    )

@app.post("/chat/start")
async def start_chat_session():
    """开始聊天会话"""
    try:
        session_id = str(uuid.uuid4())
        
        # 初始化会话状态
        chat_sessions[session_id] = {
            "session_id": session_id,
            "step": "jd_input",
            "jd_text": "",
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "requirement_node": RequirementConfirmationNode(),
            "requirement_state": None
        }
        
        return JSONResponse({
            "session_id": session_id,
            "step": "jd_input",
            "message": "您好！我是HR智能助手。请告诉我您要招聘的职位信息，包括职位名称、技能要求、工作经验等。您也可以直接粘贴完整的JD内容。"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/message")
async def process_chat_message(
    session_id: str = Form(...),
    message: str = Form(...),
    step: str = Form(...)
):
    """处理聊天消息"""
    try:
        if session_id not in chat_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = chat_sessions[session_id]
        
        # 保存用户消息
        session["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # 根据当前步骤处理消息
        if step == "jd_input":
            # 处理JD输入 - 开始交互式确认
            session["jd_text"] = message
            
            # 创建需求确认状态
            requirement_state = RequirementConfirmationState(jd_text=message)
            session["requirement_state"] = requirement_state.model_dump()
            
            # 使用需求确认节点开始交互
            requirement_node = session["requirement_node"]
            result = requirement_node.process(requirement_state)
            
            # 更新session中的状态
            session["requirement_state"] = requirement_state.model_dump()
            
            # 保存AI回复
            session["messages"].append({
                "role": "assistant", 
                "content": result["message"],
                "timestamp": datetime.now().isoformat()
            })
            
            return JSONResponse({
                "status": "success",
                "message": result["message"],
                "step": "requirement_confirmation",
                "need_files": False,
                "completed": False
            })
        
        elif step == "requirement_confirmation":
            # 继续需求确认对话
            requirement_state_dict = session["requirement_state"]
            requirement_state = RequirementConfirmationState(**requirement_state_dict)
            requirement_node = session["requirement_node"]
            
            # 处理用户输入
            result = requirement_node.process(requirement_state, message)
            
            # 更新session中的状态
            session["requirement_state"] = requirement_state.model_dump()
            
            # 保存AI回复
            session["messages"].append({
                "role": "assistant",
                "content": result["message"],
                "timestamp": datetime.now().isoformat()
            })
            
            # 检查是否完成
            if result.get("is_complete", False):
                session["job_requirement"] = result["job_requirement"].model_dump()
                return JSONResponse({
                    "status": "success",
                    "message": result["message"],
                    "step": "file_upload",
                    "need_files": True,
                    "completed": False
                })
            else:
                return JSONResponse({
                    "status": "success",
                    "message": result["message"],
                    "step": "requirement_confirmation",
                    "need_files": False,
                    "completed": False
                })
        
        else:
            # 处理其他步骤
            response_message = "请按照提示继续操作。"
            
            session["messages"].append({
                "role": "assistant",
                "content": response_message,
                "timestamp": datetime.now().isoformat()
            })
            
            return JSONResponse({
                "status": "success",
                "message": response_message,
                "step": step,
                "need_files": False,
                "completed": False
            })
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/upload")
async def upload_chat_files(
    session_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """处理聊天中的文件上传"""
    try:
        if session_id not in chat_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = chat_sessions[session_id]
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 保存上传的文件
        upload_dir = Path("web_interface/static/uploads") / task_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        for file in files:
            if file.filename:
                file_path = upload_dir / file.filename
                content = await file.read()
                
                with open(file_path, "wb") as f:
                    f.write(content)
                
                saved_files.append(str(file_path))
        
        # 初始化任务状态
        task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "开始处理...",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat()
        }
        
        # 在后台处理任务
        asyncio.create_task(
            process_chat_evaluation_task(task_id, session_id, saved_files)
        )
        
        return JSONResponse({
            "status": "success",
            "task_id": task_id,
            "file_count": len(saved_files),
            "message": "文件上传成功，开始处理"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_chat_evaluation_task(task_id: str, session_id: str, resume_files: List[str]):
    """处理聊天中的评估任务"""
    try:
        # 更新状态
        task_status[task_id]["progress"] = 10
        task_status[task_id]["message"] = "正在处理JD和简历文件..."
        
        # 获取已确认的JobRequirement（从指定会话中获取）
        if session_id not in chat_sessions:
            raise ValueError("会话不存在")
            
        session = chat_sessions[session_id]
        if not session.get("job_requirement"):
            raise ValueError("未找到已确认的招聘需求，请重新开始聊天流程")
        
        from src.models import JobRequirement
        job_req_dict = session["job_requirement"]
        job_requirement = JobRequirement(**job_req_dict)
        
        # 运行工作流 - 使用Web版本跳过交互式需求确认
        result = await workflow.run_web_workflow(job_requirement, resume_files)
        
        # 更新状态
        task_status[task_id]["progress"] = 100
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["message"] = "处理完成"
        # 使用序列化函数避免JSON序列化错误
        task_status[task_id]["result"] = serialize_workflow_result(result)
        
        # 清理上传的文件
        try:
            upload_dir = Path("web_interface/static/uploads") / task_id
            if upload_dir.exists():
                import shutil
                shutil.rmtree(upload_dir)
        except:
            pass
            
    except Exception as e:
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["error"] = str(e)
        task_status[task_id]["message"] = f"处理失败: {str(e)}"

@app.get("/chat/status/{task_id}")
async def get_chat_task_status(task_id: str):
    """获取聊天任务状态"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return JSONResponse(task_status[task_id])

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    print("🚀 HR智能体Web界面启动成功")
    print("📝 访问 http://localhost:8000 开始使用")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)