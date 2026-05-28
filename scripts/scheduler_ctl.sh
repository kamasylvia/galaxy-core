#!/bin/bash
# Scheduler 控制脚本
# 用于启动/停止/查看自动同步进程

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/.scheduler.pid"
LOG_DIR="$PROJECT_DIR/logs"

# 环境选择：dev 或 production
ENV="${GALAXY_CONFIG_ENV:-production}"

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

is_running() {
    pid=$(get_pid)
    if [ -n "$pid" ]; then
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

start() {
    if is_running; then
        echo "Scheduler 已在运行 (PID: $(get_pid))"
        exit 0
    fi

    mkdir -p "$LOG_DIR"

    cd "$PROJECT_DIR"

    # 激活虚拟环境
    if [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
        source "$PROJECT_DIR/.venv/bin/activate"
    fi

    echo "启动 Scheduler (环境: $ENV)..."

    if [ "$ENV" = "dev" ]; then
        nohup python -m galaxy_db_sync.scheduler > "$LOG_DIR/scheduler.out" 2>&1 &
    else
        GALAXY_CONFIG_ENV=production nohup python -m galaxy_db_sync.scheduler > "$LOG_DIR/scheduler.out" 2>&1 &
    fi

    pid=$!
    echo $pid > "$PID_FILE"
    sleep 2

    if is_running; then
        echo "Scheduler 已启动 (PID: $pid)"
        echo "日志输出: $LOG_DIR/scheduler.out"
    else
        echo "启动失败，请检查日志: $LOG_DIR/scheduler.out"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop() {
    if ! is_running; then
        echo "Scheduler 未运行"
        rm -f "$PID_FILE"
        exit 0
    fi

    pid=$(get_pid)
    echo "停止 Scheduler (PID: $pid)..."

    # 先发送 SIGTERM，优雅关闭
    kill "$pid" 2>/dev/null || true

    # 等待最多 10 秒
    for i in {1..10}; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # 如果还在运行，强制终止
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "进程未响应，强制终止..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "Scheduler 已停止"
}

status() {
    if is_running; then
        pid=$(get_pid)
        echo "Scheduler 运行中 (PID: $pid)"
        echo "环境: $ENV"
        ps -p "$pid" -o pid,etime,cmd --no-headers 2>/dev/null || true
    else
        echo "Scheduler 未运行"
        if [ -f "$PID_FILE" ]; then
            echo "(PID 文件存在但进程已终止，可能是异常退出)"
        fi
    fi
}

restart() {
    stop
    sleep 1
    start
}

case "${1:-status}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    restart)
        restart
        ;;
    *)
        echo "用法: $0 {start|stop|status|restart}"
        echo ""
        echo "环境变量:"
        echo "  GALAXY_CONFIG_ENV=dev    使用开发环境配置"
        echo "  GALAXY_CONFIG_ENV=production  使用生产环境配置 (默认)"
        exit 1
        ;;
esac