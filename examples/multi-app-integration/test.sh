#!/bin/bash

echo "🚀 启动多应用 OpenTelemetry 集成测试"

# 检查观测平台是否运行
echo "📡 检查观测平台状态..."
if ! curl -s http://localhost:13133/ > /dev/null; then
    echo "❌ OpenTelemetry Collector 未运行，请先启动观测平台："
    echo "   cd ../../ && ./manage.sh start"
    exit 1
fi

echo "✅ 观测平台运行正常"

# 基础 URL
BASE_URL="http://localhost:8000"

# 等待应用启动
echo "⏳ 等待应用启动..."
sleep 2

# 函数：执行测试并显示结果
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo "🔗 测试: $description"
    echo "   $method $endpoint"
    
    if [ "$method" = "POST" ]; then
        response=$(curl -s -w "%{http_code}" -X POST "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data" -o /tmp/response.json)
    else
        response=$(curl -s -w "%{http_code}" "$BASE_URL$endpoint" -o /tmp/response.json)
    fi
    
    http_code=${response: -3}
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo "   ✅ 成功 ($http_code)"
    elif [ "$http_code" -ge 500 ]; then
        echo "   ⚠️  预期错误 ($http_code) - 用于错误日志演示"
    else
        echo "   ❌ 失败 ($http_code)"
    fi
    
    echo "   📄 响应: $(head -c 100 /tmp/response.json)..."
    echo ""
    sleep 1
}

echo "🧪 开始执行测试用例..."
echo ""

# 基础健康检查
test_endpoint "GET" "/" "" "应用健康检查"

# 用户查询测试
test_endpoint "GET" "/api/users/user123" "" "用户信息查询 - 包含数据库和外部服务调用"

test_endpoint "GET" "/api/users/user456" "" "另一个用户查询 - 验证不同的 trace"

# 用户操作测试
test_endpoint "POST" "/api/users/user123/actions" \
    '{"type": "login", "timestamp": "2024-01-01T10:00:00", "client": "web"}' \
    "用户登录操作 - 复杂业务流程追踪"

test_endpoint "POST" "/api/users/user456/actions" \
    '{"type": "purchase", "amount": 99.99, "product_id": "laptop001"}' \
    "用户购买操作 - 支付流程追踪"

test_endpoint "POST" "/api/users/user789/actions" \
    '{"type": "unknown_action", "data": "test"}' \
    "未知操作类型 - 警告日志演示"

# 指标演示
test_endpoint "GET" "/api/metrics-demo" "" "多级别日志演示"

# 错误演示
echo "🚨 错误测试 - 以下请求会故意产生错误用于演示错误追踪:"
for i in {1..3}; do
    test_endpoint "GET" "/api/error-demo" "" "错误演示 #$i - 随机错误类型"
done

echo "✅ 测试完成！"
echo ""
echo "📊 查看结果:"
echo "1. Grafana: http://localhost:3100 (admin/admin123)"
echo "2. OpenTelemetry Collector Health: http://localhost:13133/"
echo "3. OpenTelemetry Collector Metrics: http://localhost:8888/metrics"
echo ""
echo "🔍 在 Grafana 中的查询建议:"
echo '   查看所有日志: {service_name="multi-app-demo"}'
echo '   查看错误日志: {service_name="multi-app-demo"} | json | level="error"'
echo '   查看特定 trace: {service_name="multi-app-demo"} | json | trace_id="your_trace_id"'
echo ""
echo "💡 注意: 数据可能需要 1-2 分钟才会出现在 Grafana 中"