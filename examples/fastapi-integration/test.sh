#!/bin/bash

# 测试脚本 - 生成示例日志数据

echo "开始测试 FastAPI 应用并生成日志..."

# 基础 URL
BASE_URL="http://localhost:8000"

# 测试基本端点
echo "测试基本端点..."
curl -s "$BASE_URL/" > /dev/null
curl -s "$BASE_URL/health" > /dev/null

# 测试 trace 端点
echo "测试 trace 端点..."
for i in {1..5}; do
    curl -s "$BASE_URL/trace/item$i" > /dev/null
done

# 测试用户操作端点
echo "测试用户操作端点..."
curl -s -X POST "$BASE_URL/user/123/action" \
  -H "Content-Type: application/json" \
  -d '{"type": "login", "timestamp": "2023-01-01T10:00:00"}' > /dev/null

curl -s -X POST "$BASE_URL/user/456/action" \
  -H "Content-Type: application/json" \
  -d '{"type": "purchase", "item": "laptop", "amount": 1500}' > /dev/null

# 测试指标端点
echo "测试指标端点..."
curl -s "$BASE_URL/metrics" > /dev/null

# 测试错误端点（会生成错误日志）
echo "测试错误端点..."
curl -s "$BASE_URL/error" > /dev/null || true

echo "测试完成！检查 logs/app.log 文件查看生成的日志。"