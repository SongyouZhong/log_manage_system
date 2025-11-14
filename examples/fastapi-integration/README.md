# FastAPI + OpenTelemetry 集成示例

这个目录包含了一个完整的 FastAPI 应用示例，展示了如何集成 OpenTelemetry 分布式追踪和结构化日志，与 Loki + Promtail + Grafana 日志观测平台完美配合。

## 🏗️ 功能特性

- ✅ **OpenTelemetry 分布式追踪**: 完整的 trace 和 span 支持
- ✅ **结构化日志**: 使用 structlog 生成 JSON 格式日志
- ✅ **自动集成**: FastAPI 自动 instrumentation
- ✅ **错误处理**: 完整的异常追踪和日志记录
- ✅ **健康检查**: 内置健康检查端点
- ✅ **测试工具**: 包含自动化测试脚本

## 📋 依赖要求

### 安装依赖

```bash
cd examples/fastapi-integration
pip install -r requirements.txt
```

### requirements.txt 内容

```
fastapi==0.104.1
uvicorn==0.24.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-instrumentation-fastapi==0.42b0
opentelemetry-instrumentation-logging==0.42b0
opentelemetry-exporter-otlp==1.21.0
structlog==23.2.0
```

## 🚀 快速开始

### 1. 确保日志观测平台运行

```bash
# 返回到项目根目录
cd ../..

# 启动日志观测平台（如果还没启动）
./manage.sh start
```

平台服务地址：
- **Grafana**: http://localhost:3100 (admin/admin123)
- **Loki API**: http://localhost:3101

### 2. 启动 FastAPI 应用

```bash
# 返回到示例目录
cd examples/fastapi-integration

# 启动应用
python main.py
```

应用将在 http://localhost:8000 启动并开始记录日志到 `../../logs/app.log`。

### 3. 运行测试脚本

```bash
# 生成示例日志数据
chmod +x test.sh
./test.sh
```

## 📡 API 端点说明

| 端点 | 方法 | 说明 | 日志特性 |
|------|------|------|----------|
| `/` | GET | 基础端点 | 基本信息日志 |
| `/health` | GET | 健康检查 | 服务状态日志 |
| `/error` | GET | 错误模拟 | 异常和错误日志 |
| `/trace/{item_id}` | GET | 分布式追踪示例 | 包含 trace_id 和 span_id |
| `/metrics` | GET | 多级别日志示例 | DEBUG, INFO, WARNING 级别 |
| `/user/{user_id}/action` | POST | 用户操作记录 | 结构化数据和追踪 |

### 测试示例

```bash
# 基础测试
curl http://localhost:8000/

# 健康检查
curl http://localhost:8000/health

# 分布式追踪测试
curl http://localhost:8000/trace/user123

# 用户操作测试
curl -X POST http://localhost:8000/user/123/action \
  -H "Content-Type: application/json" \
  -d '{"type": "login", "timestamp": "2024-01-01T10:00:00"}'

# 错误测试（生成错误日志）
curl http://localhost:8000/error
```

## 📊 日志格式和结构

### JSON 日志格式
```json
{
  "timestamp": "2024-01-01T10:00:00.000Z",
  "level": "info",
  "logger": "__main__",
  "message": "开始处理项目",
  "service_name": "fastapi-demo",
  "endpoint": "/trace",
  "item_id": "user123",
  "operation": "start",
  "trace_id": "abc123def456...",
  "span_id": "789xyz..."
}
```

### 关键字段说明
- `service_name`: 服务标识，用于在 Grafana 中筛选
- `trace_id`: OpenTelemetry 追踪 ID，用于关联分布式请求
- `span_id`: 当前操作的 span ID
- `endpoint`: API 端点路径
- `level`: 日志级别（debug, info, warning, error）

## 📈 在 Grafana 中查看日志

### 1. 访问 Grafana
- URL: http://localhost:3100
- 用户名: admin
- 密码: admin123

### 2. 常用查询

**查看所有 FastAPI 日志**:
```logql
{job="fastapi-logs"} | json
```

**筛选特定服务的日志**:
```logql
{job="fastapi-logs"} | json | service_name="fastapi-demo"
```

**查看错误日志**:
```logql
{job="fastapi-logs"} | json | level="error"
```

**追踪特定请求**:
```logql
{job="fastapi-logs"} | json | trace_id="your_trace_id"
```

**统计错误频率**:
```logql
sum(count_over_time({job="fastapi-logs"} | json | level="error" [5m]))
```

### 3. 使用预配置仪表板

项目包含预配置的 "FastAPI 日志监控" 仪表板，提供：
- 请求数量统计
- 错误率监控
- 响应时间分布
- 服务健康状况
- 热点端点分析

## 🔧 自定义配置

### 修改日志级别

在 `main.py` 中修改：
```python
# 修改根日志级别
root_logger.setLevel(logging.DEBUG)  # 改为 DEBUG 级别
```

### 添加自定义字段

```python
# 在日志中添加自定义信息
logger.info("自定义事件", 
    custom_field="自定义值",
    user_id=user_id,
    operation_type="business"
)
```

### 配置不同的日志输出

```python
# 添加错误日志单独文件
error_handler = logging.FileHandler(f'{log_dir}/error.log')
error_handler.setLevel(logging.ERROR)
root_logger.addHandler(error_handler)
```

## 🐳 Docker 集成

### Dockerfile 示例
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .

# 确保日志目录存在
RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "main.py"]
```

### docker-compose.yml 集成
```yaml
services:
  fastapi-app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ../../logs:/app/logs  # 重要：映射到主项目的日志目录
    environment:
      - SERVICE_NAME=fastapi-demo
    depends_on:
      - loki
    networks:
      - logging
```

## 🔍 故障排除

### 常见问题

1. **日志不出现在 Grafana**
   - 检查 `../../logs/app.log` 是否生成
   - 确认 Promtail 服务运行正常：`../../manage.sh status`
   - 检查日志格式是否为有效 JSON

2. **Trace 信息缺失**
   - 确认请求包含 OpenTelemetry context
   - 检查 structlog 配置中的 `add_trace_info` 处理器

3. **端口冲突**
   - FastAPI 默认端口 8000
   - 如需修改，在 `main.py` 中更改 `uvicorn.run()` 的 port 参数

### 调试命令

```bash
# 查看日志文件内容
tail -f ../../logs/app.log

# 检查 JSON 格式
cat ../../logs/app.log | jq .

# 测试 Loki 连接
curl -G -s "http://localhost:3101/loki/api/v1/labels"
```

## 🚀 扩展建议

1. **添加认证中间件**: 记录用户身份信息
2. **性能监控**: 添加请求处理时间记录
3. **数据库集成**: 记录数据库查询日志
4. **缓存监控**: 记录缓存命中率
5. **业务指标**: 记录业务相关的自定义指标

## 📝 最佳实践

1. **统一服务标识**: 始终使用相同的 `service_name`
2. **结构化数据**: 避免在消息中嵌入动态数据，使用独立字段
3. **错误上下文**: 记录足够的上下文信息用于问题诊断
4. **日志级别**: 正确使用 DEBUG, INFO, WARNING, ERROR 级别
5. **性能考虑**: 避免在高频路径中记录过多调试信息