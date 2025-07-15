#!/usr/bin/env python3
"""
启动HR智能体Web界面
"""
import uvicorn
import os
from pathlib import Path

def main():
    """启动Web服务器"""
    # 确保在项目根目录运行
    os.chdir(Path(__file__).parent)
    
    # 检查环境变量
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  警告: 未设置 OPENAI_API_KEY 环境变量")
        print("   请确保在 .env 文件中设置了 OPENAI_API_KEY")
        print("   或者使用命令: export OPENAI_API_KEY=your_api_key")
    
    print("🚀 启动HR智能体Web界面...")
    print("📝 请在浏览器中访问: http://localhost:8000")
    print("🔧 按 Ctrl+C 停止服务器")
    
    # 启动服务器
    uvicorn.run(
        "web_interface.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["web_interface", "src"]
    )

if __name__ == "__main__":
    main()