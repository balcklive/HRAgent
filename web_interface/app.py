#!/usr/bin/env python3
"""
HR AI Web Interface - FastAPI Application
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
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Add project root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflow_optimized import OptimizedHRAgentWorkflow
from src.models import JobRequirement, WorkflowState
from src.nodes import RequirementConfirmationNode
from src.models import RequirementConfirmationState

app = FastAPI(
    title="HR AI Resume Screening System",
    description="AI-based intelligent resume screening and evaluation system",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="web_interface/static"), name="static")
templates = Jinja2Templates(directory="web_interface/templates")

# Workflow instance
workflow = OptimizedHRAgentWorkflow()

# Task status storage
task_status = {}

# Chat session storage
chat_sessions = {}

# Streaming session storage
streaming_sessions = {}

# Requirement confirmation node
requirement_node = RequirementConfirmationNode()

def serialize_workflow_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize workflow results to avoid JSON serialization errors"""
    # Serialize complex objects to avoid JSON serialization errors
    evaluations = result.get("evaluations", [])
    if evaluations:
        # If evaluations is a list of objects, convert to list of dictionaries
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
        "report": result.get("final_report", ""),  # Unified use of report field
        "report_file": result.get("report_file", ""),
        "evaluations": evaluations,
        "job_requirement": job_requirement,
        "scoring_dimensions": scoring_dimensions,
        "total_duration": result.get("total_duration", 0)
    }

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    jd_text: str = Form(...),
    resume_files: List[UploadFile] = File(...)
):
    """Handle file upload and JD text"""
    try:
        # Validate input
        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="JD text cannot be empty")
        
        if not resume_files:
            raise HTTPException(status_code=400, detail="Please upload at least one resume file")
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Initialize task status
        task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Starting processing...",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat()
        }
        
        # Save uploaded files
        upload_dir = Path("web_interface/static/uploads") / task_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        for file in resume_files:
            if file.filename:
                file_path = upload_dir / file.filename
                content = await file.read()
                
                # Save file
                with open(file_path, "wb") as f:
                    f.write(content)
                
                saved_files.append(str(file_path))
        
        # Process task in background
        background_tasks.add_task(
            process_evaluation_task,
            task_id,
            jd_text,
            saved_files
        )
        
        return JSONResponse({
            "task_id": task_id,
            "message": "File upload successful, processing started",
            "files_count": len(saved_files)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_evaluation_task(task_id: str, jd_text: str, resume_files: List[str]):
    """Background processing of evaluation tasks"""
    try:
        # 更新状态
        task_status[task_id]["progress"] = 10
        task_status[task_id]["message"] = "Processing JD and resume files..."
        
        # For traditional upload, use automatic requirement confirmation
        # Here directly call the original workflow method, let it automatically extract requirements
        result = await workflow.run_optimized_workflow(jd_text, resume_files)
        
        # 更新状态
        task_status[task_id]["progress"] = 100
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["message"] = "Processing completed"
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
    """Get task status"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return JSONResponse(task_status[task_id])

@app.get("/result/{task_id}")
async def get_result(request: Request, task_id: str):
    """Get processing result page"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_status[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not yet completed")
    
    result = task["result"]
    
    # Prepare template data
    template_data = {
        "request": request,
        "task_id": task_id,
        "result": result,
        "created_at": task["created_at"]
    }
    
    return templates.TemplateResponse("result.html", template_data)

@app.get("/download/{task_id}")
async def download_report(task_id: str):
    """Download evaluation report"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_status[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not yet completed")
    
    # Return report file content
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
    """Start chat session"""
    try:
        session_id = str(uuid.uuid4())
        
        # Initialize session state
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
            "message": "Hello! I'm your HR AI Assistant. Please tell me about the position you're recruiting for, including job title, skill requirements, work experience, etc. You can also paste the complete JD content directly."
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/message/stream")
async def process_chat_message_stream(
    session_id: str = Form(...),
    message: str = Form(...),
    step: str = Form(...)
):
    """Process chat messages with streaming"""
    try:
        if session_id not in chat_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = chat_sessions[session_id]
        
        # Save user message
        session["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        async def generate():
            if step == "jd_input":
                # Create requirement confirmation state
                requirement_state = RequirementConfirmationState(jd_text=message)
                session["requirement_state"] = requirement_state.model_dump()
                session["jd_text"] = message
                
                # Stream processing
                requirement_node = session["requirement_node"]
                async for chunk in requirement_node.process_stream(requirement_state):
                    # Update session state
                    session["requirement_state"] = requirement_state.model_dump()
                    
                    # Add step information
                    if chunk.get("type") == "continue":
                        chunk["step"] = "requirement_confirmation"
                    elif chunk.get("type") == "complete":
                        chunk["step"] = "file_upload"
                        chunk["need_files"] = True
                    
                    # Send SSE data
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
            elif step == "requirement_confirmation":
                # Continue requirement confirmation dialogue
                requirement_state_dict = session["requirement_state"]
                requirement_state = RequirementConfirmationState(**requirement_state_dict)
                requirement_node = session["requirement_node"]
                
                async for chunk in requirement_node.process_stream(requirement_state, message):
                    # Update session state
                    session["requirement_state"] = requirement_state.model_dump()
                    
                    # Check if completed
                    if chunk.get("is_complete", False):
                        session["job_requirement"] = chunk["job_requirement"]
                        chunk["step"] = "file_upload"
                        chunk["need_files"] = True
                    else:
                        chunk["step"] = "requirement_confirmation"
                    
                    yield f"data: {json.dumps(chunk)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/message")
async def process_chat_message(
    session_id: str = Form(...),
    message: str = Form(...),
    step: str = Form(...)
):
    """Process chat messages (fallback)"""
    try:
        if session_id not in chat_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = chat_sessions[session_id]
        
        # Save user message
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
    """Handle file uploads in chat"""
    try:
        if session_id not in chat_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = chat_sessions[session_id]
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Save uploaded files
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
        
        # Initialize task status
        task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Starting processing...",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat()
        }
        
        # Process task in background
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

@app.post("/chat/upload/stream")
async def upload_chat_files_stream(
    session_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """Handle file uploads in chat (streaming version)"""
    try:
        if session_id not in chat_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = chat_sessions[session_id]
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Save uploaded files
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
        
        # 初始化流式任务状态
        streaming_sessions[task_id] = {
            "status": "processing",
            "session_id": session_id,
            "files": saved_files,
            "created_at": datetime.now().isoformat()
        }
        
        # 创建流式响应
        async def generate_stream():
            try:
                # 获取作业需求
                job_requirement_dict = session.get("job_requirement")
                if not job_requirement_dict:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Job requirement information not found'})}\n\n"
                    return
                
                # 将字典转换为JobRequirement对象
                try:
                    job_requirement = JobRequirement(**job_requirement_dict)
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Job requirement data format error: {str(e)}'})}\n\n"
                    return
                
                # 创建工作流实例
                workflow = OptimizedHRAgentWorkflow()
                
                # 创建进度回调队列
                progress_queue = asyncio.Queue()
                
                # 创建进度回调
                async def progress_callback(progress_data):
                    await progress_queue.put(progress_data)
                
                # 启动工作流任务
                workflow_task = asyncio.create_task(
                    workflow.run_web_workflow_stream(job_requirement, saved_files, progress_callback)
                )
                
                # 处理进度更新
                while not workflow_task.done():
                    try:
                        # 等待进度更新，设置超时避免阻塞
                        progress_data = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                        yield f"data: {json.dumps({'type': 'progress', **progress_data})}\n\n"
                    except asyncio.TimeoutError:
                        # 发送心跳以保持连接
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                
                # 处理剩余的进度更新
                while not progress_queue.empty():
                    progress_data = await progress_queue.get()
                    yield f"data: {json.dumps({'type': 'progress', **progress_data})}\n\n"
                
                # 获取工作流结果
                result = await workflow_task
                
                # 序列化结果以避免JSON序列化错误
                serialized_result = serialize_workflow_result(result)
                
                # 发送完成结果
                yield f"data: {json.dumps({'type': 'complete', 'result': serialized_result})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            finally:
                # 清理流式会话
                if task_id in streaming_sessions:
                    del streaming_sessions[task_id]
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Task-ID": task_id
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_chat_evaluation_task(task_id: str, session_id: str, resume_files: List[str]):
    """Process evaluation tasks in chat"""
    try:
        # 更新状态
        task_status[task_id]["progress"] = 10
        task_status[task_id]["message"] = "Processing JD and resume files..."
        
        # 获取已确认的JobRequirement（从指定会话中获取）
        if session_id not in chat_sessions:
            raise ValueError("Session not found")
            
        session = chat_sessions[session_id]
        if not session.get("job_requirement"):
            raise ValueError("Confirmed job requirements not found, please restart the chat process")
        
        from src.models import JobRequirement
        job_req_dict = session["job_requirement"]
        job_requirement = JobRequirement(**job_req_dict)
        
        # 运行工作流 - 使用Web版本跳过交互式需求确认
        result = await workflow.run_web_workflow(job_requirement, resume_files)
        
        # 更新状态
        task_status[task_id]["progress"] = 100
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["message"] = "Processing completed"
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
    """Get chat task status"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return JSONResponse(task_status[task_id])

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    print("🚀 HR AI Web Interface started successfully")
    print("📝 Visit http://localhost:8000 to start using")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)