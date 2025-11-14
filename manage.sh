#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    mkdir -p logs
    mkdir -p config/{loki,promtail,grafana,otel-collector}
    mkdir -p config/grafana/{datasources,dashboards,dashboard-configs}
}

# 检查 Docker 和 Docker Compose
check_prerequisites() {
    log_info "检查先决条件..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    log_info "先决条件检查通过"
}

# 启动服务
start_services() {
    log_info "启动 OpenTelemetry + Loki + Promtail + Grafana 观测平台..."
    
    # 检查是否使用新版 docker compose 命令
    if command -v docker compose &> /dev/null; then
        docker compose up -d
    else
        docker-compose up -d
    fi
    
    if [ $? -eq 0 ]; then
        log_info "服务启动成功！"
        echo ""
        echo "访问地址："
        echo "- Grafana: http://localhost:3100 (admin/admin123)"
        echo "- Loki API: http://localhost:3101"
        echo "- OpenTelemetry Collector:"
        echo "  * OTLP gRPC: localhost:4317"
        echo "  * OTLP HTTP: localhost:4318"
        echo "  * Health Check: http://localhost:13133"
        echo ""
        log_info "等待服务完全启动（大约30秒）..."
        sleep 30
        check_services
    else
        log_error "服务启动失败"
        exit 1
    fi
}

# 停止服务
stop_services() {
    log_info "停止日志观测平台..."
    
    if command -v docker compose &> /dev/null; then
        docker compose down
    else
        docker-compose down
    fi
}

# 重启服务
restart_services() {
    log_info "重启日志观测平台..."
    stop_services
    sleep 5
    start_services
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."
    
    services=("otel-collector" "loki" "promtail" "grafana")
    
    for service in "${services[@]}"; do
        if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$service.*Up"; then
            log_info "$service: 运行中 ✅"
        else
            log_warn "$service: 未运行 ❌"
        fi
    done
}

# 查看日志
view_logs() {
    if [ -z "$1" ]; then
        log_info "显示所有服务日志..."
        if command -v docker compose &> /dev/null; then
            docker compose logs -f
        else
            docker-compose logs -f
        fi
    else
        log_info "显示 $1 服务日志..."
        docker logs -f "$1"
    fi
}

# 清理数据
clean_data() {
    read -p "确定要清理所有数据吗？这将删除所有日志和仪表板配置 (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "清理数据..."
        stop_services
        docker volume rm dev_ops_loki-data dev_ops_grafana-data 2>/dev/null || true
        log_info "数据清理完成"
    else
        log_info "取消清理操作"
    fi
}

# 显示帮助信息
show_help() {
    echo "OpenTelemetry + Loki + Promtail + Grafana 观测平台管理脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动所有服务"
    echo "  stop      停止所有服务"
    echo "  restart   重启所有服务"
    echo "  status    检查服务状态"
    echo "  logs      查看所有服务日志"
    echo "  logs <service>  查看指定服务日志 (otel-collector|loki|promtail|grafana)"
    echo "  clean     清理所有数据"
    echo "  help      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start"
    echo "  $0 logs grafana"
    echo "  $0 status"
}

# 主程序
main() {
    case "${1:-help}" in
        start)
            check_prerequisites
            create_directories
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            check_services
            ;;
        logs)
            view_logs "$2"
            ;;
        clean)
            clean_data
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"