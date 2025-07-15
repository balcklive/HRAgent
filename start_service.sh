#!/bin/bash
# Author: Peng Fei
# 一键启动HR智能体Web服务脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 常量定义
SERVICE_NAME="HR智能体Web服务"
PORT=8000
PID_FILE="/tmp/hragent_web.pid"
LOG_FILE="/tmp/hragent_web.log"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查服务是否已经在运行
check_service_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi
    return 1
}

# 检查端口是否被占用
check_port_available() {
    if lsof -i :$PORT > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# 停止已运行的服务
stop_existing_service() {
    print_info "检查是否有服务正在运行..."
    
    if check_service_running; then
        PID=$(cat "$PID_FILE")
        print_warning "发现服务正在运行 (PID: $PID)，正在停止..."
        kill -TERM "$PID" 2>/dev/null
        sleep 2
        if ps -p "$PID" > /dev/null 2>&1; then
            print_warning "服务未响应，强制停止..."
            kill -KILL "$PID" 2>/dev/null
        fi
        rm -f "$PID_FILE"
        print_success "已停止现有服务"
    fi
    
    # 检查端口占用
    if check_port_available; then
        print_warning "端口 $PORT 被占用，正在清理..."
        lsof -ti :$PORT | xargs kill -KILL 2>/dev/null
        sleep 1
    fi
}

# 检查环境
check_environment() {
    print_info "检查运行环境..."
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装"
        exit 1
    fi
    
    # 检查uv
    if ! command -v uv &> /dev/null; then
        print_error "uv 包管理器未安装"
        exit 1
    fi
    
    # 检查项目文件
    if [ ! -f "start_web.py" ]; then
        print_error "未找到 start_web.py 文件"
        exit 1
    fi
    
    # 检查环境变量
    if [ -z "$OPENAI_API_KEY" ]; then
        print_warning "未设置 OPENAI_API_KEY 环境变量"
        print_info "请确保在 .env 文件中设置了 OPENAI_API_KEY"
    fi
    
    print_success "环境检查通过"
}

# 启动服务
start_service() {
    print_info "启动 $SERVICE_NAME..."
    
    # 切换到项目根目录
    cd "$(dirname "$0")"
    
    # 启动服务
    nohup uv run python start_web.py > "$LOG_FILE" 2>&1 &
    SERVICE_PID=$!
    
    # 保存PID
    echo $SERVICE_PID > "$PID_FILE"
    
    # 等待服务启动
    print_info "等待服务启动..."
    sleep 3
    
    # 检查服务是否成功启动
    if ps -p $SERVICE_PID > /dev/null 2>&1; then
        print_success "$SERVICE_NAME 启动成功！"
        print_info "服务PID: $SERVICE_PID"
        print_info "日志文件: $LOG_FILE"
        print_info "访问地址: http://localhost:$PORT"
        print_info "按 Ctrl+C 停止服务"
        
        # 显示实时日志
        print_info "显示服务日志 (按 Ctrl+C 退出):"
        tail -f "$LOG_FILE"
    else
        print_error "服务启动失败"
        print_info "请检查日志文件: $LOG_FILE"
        exit 1
    fi
}

# 主函数
main() {
    echo "=========================================="
    echo "    HR智能体Web服务启动脚本"
    echo "=========================================="
    
    # 检查环境
    check_environment
    
    # 停止现有服务
    stop_existing_service
    
    # 启动服务
    start_service
}

# 捕获Ctrl+C信号
trap 'echo -e "\n${YELLOW}[INFO]${NC} 收到停止信号，正在退出..."; exit 0' INT

# 运行主函数
main "$@" 