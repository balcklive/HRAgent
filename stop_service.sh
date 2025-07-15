#!/bin/bash
# Author: Peng Fei
# 一键停止HR智能体Web服务脚本

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

# 检查服务是否在运行
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
check_port_occupied() {
    if lsof -i :$PORT > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# 优雅停止服务
stop_service_gracefully() {
    local PID=$1
    print_info "正在优雅停止服务 (PID: $PID)..."
    
    # 发送TERM信号
    kill -TERM "$PID" 2>/dev/null
    
    # 等待服务停止
    local count=0
    while [ $count -lt 10 ]; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            print_success "服务已优雅停止"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    
    return 1
}

# 强制停止服务
force_stop_service() {
    local PID=$1
    print_warning "服务未响应，正在强制停止 (PID: $PID)..."
    
    # 发送KILL信号
    kill -KILL "$PID" 2>/dev/null
    
    # 等待服务停止
    sleep 2
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        print_success "服务已强制停止"
        return 0
    else
        print_error "无法停止服务"
        return 1
    fi
}

# 清理端口占用
cleanup_port() {
    if check_port_occupied; then
        print_warning "发现端口 $PORT 仍被占用，正在清理..."
        lsof -ti :$PORT | xargs kill -KILL 2>/dev/null
        sleep 1
        
        if check_port_occupied; then
            print_error "无法清理端口 $PORT"
            return 1
        else
            print_success "端口 $PORT 已清理"
            return 0
        fi
    fi
    return 0
}

# 清理临时文件
cleanup_files() {
    print_info "清理临时文件..."
    
    if [ -f "$PID_FILE" ]; then
        rm -f "$PID_FILE"
        print_info "已删除PID文件: $PID_FILE"
    fi
    
    if [ -f "$LOG_FILE" ]; then
        print_info "日志文件位置: $LOG_FILE"
        print_info "如需查看日志，请运行: cat $LOG_FILE"
    fi
}

# 显示服务状态
show_service_status() {
    print_info "检查服务状态..."
    
    if check_service_running; then
        PID=$(cat "$PID_FILE")
        print_warning "服务正在运行 (PID: $PID)"
        return 0
    elif check_port_occupied; then
        print_warning "端口 $PORT 被占用，但PID文件不存在"
        return 0
    else
        print_info "服务未运行"
        return 1
    fi
}

# 停止服务
stop_service() {
    print_info "停止 $SERVICE_NAME..."
    
    # 检查服务状态
    if ! show_service_status; then
        print_info "没有发现运行中的服务"
        cleanup_files
        return 0
    fi
    
    # 通过PID文件停止服务
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            if ! stop_service_gracefully "$PID"; then
                force_stop_service "$PID"
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # 清理端口占用
    cleanup_port
    
    # 清理文件
    cleanup_files
    
    print_success "$SERVICE_NAME 已停止"
}

# 显示帮助信息
show_help() {
    echo "=========================================="
    echo "    HR智能体Web服务停止脚本"
    echo "=========================================="
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help     显示此帮助信息"
    echo "  -s, --status   显示服务状态"
    echo "  -f, --force    强制停止服务"
    echo ""
    echo "示例:"
    echo "  $0             停止服务"
    echo "  $0 --status    显示服务状态"
    echo "  $0 --force     强制停止服务"
}

# 主函数
main() {
    local FORCE_MODE=false
    local STATUS_ONLY=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -s|--status)
                STATUS_ONLY=true
                shift
                ;;
            -f|--force)
                FORCE_MODE=true
                shift
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    if [ "$STATUS_ONLY" = true ]; then
        show_service_status
        exit 0
    fi
    
    if [ "$FORCE_MODE" = true ]; then
        print_warning "强制停止模式"
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            force_stop_service "$PID"
            rm -f "$PID_FILE"
        fi
        cleanup_port
        cleanup_files
        print_success "强制停止完成"
        exit 0
    fi
    
    # 正常停止流程
    stop_service
}

# 捕获Ctrl+C信号
trap 'echo -e "\n${YELLOW}[INFO]${NC} 收到停止信号，正在退出..."; exit 0' INT

# 运行主函数
main "$@" 