# Loki + Promtail + Grafana 日志观测平台

这是一个完整的日志观测平台，专门为支持 OpenTelemetry 集成的 FastAPI 项目设计。

## 🏗️ 架构组件
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────────┐
│  FastAPI App    │────│ Log Files    │────│  Promtail   │────│     Loki        │
│ (Backend)       │    │ (app.log)    │    │ (Collector) │    │  (Storage)      │
│                 │    │              │    │             │    │                 │
│ • HTTP Requests │    │ • JSON Lines │    │ • File Tail │    │ • Index Labels  │
│ • Business Logic│    │ • Structured │    │ • Parse JSON│    │ • Time Series   │
│ • Error Handling│    │ • Timestamped│    │ • Add Labels│    │ • Compression   │
│                 │    │              │    │ • Send HTTP │    │                 │
└─────────────────┘    └──────────────┘    └─────────────┘    └─────────────────┘
                                                  │                     ▲
                                                  │                     │
                                                  ▼                     │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Grafana                                           │
│                          (Visualization)                                       │
│                                                                                 │
│ • LogQL Queries      • Real-time Dashboard     • Alerting                     │
│ • Time Range Filter  • Log Stream Viewer       • User Management              │
│ • Label Filtering    • JSON Pretty Print       • Data Source Proxy            │
└─────────────────────────────────────────────────────────────────────────────────┘
### 核心组件
- **Loki**: 日志聚合和存储系统
- **Promtail**: 日志收集器，负责从多种源收集日志
- **Grafana**: 可视化和监控仪表板

### 端口配置
- Grafana: http://localhost:3100 (admin/admin123)
- Loki: http://localhost:3101
- Promtail: 9080 (内部端口)

## 🚀 快速开始

### 1. 启动平台

```bash
# 启动所有服务
./manage.sh start

# 检查服务状态
./manage.sh status
```

### 2. 访问 Grafana
- URL: http://localhost:3100
- 用户名: admin
- 密码: admin123

### 3. 预配置仪表板
平台包含两个预配置的仪表板：
- **FastAPI 日志监控**: 专门用于监控 FastAPI 应用日志
- **系统日志监控**: 系统和容器日志监控

## 📁 目录结构

```
dev_ops/
├── docker-compose.yml          # Docker Compose 配置
├── manage.sh                  # 管理脚本
├── logs/                      # 应用日志目录
├── config/
│   ├── loki/
│   │   └── loki-config.yml    # Loki 配置
│   ├── promtail/
│   │   └── promtail-config.yml # Promtail 配置
│   └── grafana/
│       ├── datasources/       # 数据源配置
│       ├── dashboards/        # 仪表板提供者配置
│       └── dashboard-configs/ # 仪表板 JSON 配置
└── README.md
```

## 🔧 FastAPI 项目集成

### 1. 安装依赖

```bash
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-logging
pip install structlog
```

### 2. FastAPI 应用代码示例

```python
# main.py
import logging
import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import json
import sys
from datetime import datetime

# OpenTelemetry 配置
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# 配置结构化日志
def add_trace_info(logger, method_name, event_dict):
    """添加 trace 信息到日志中"""
    span = trace.get_current_span()
    if span:
        span_context = span.get_span_context()
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict

# 配置 structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        add_trace_info,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# 配置日志输出到文件
file_handler = logging.FileHandler('/app/logs/app.log')
file_handler.setFormatter(logging.Formatter('%(message)s'))

logger = structlog.get_logger()
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, logging.StreamHandler(sys.stdout)]
)

app = FastAPI(title="示例 FastAPI 应用")

# 自动 instrument FastAPI
FastAPIInstrumentor.instrument_app(app)
LoggingInstrumentor().instrument()

@app.get("/")
async def root():
    logger.info("根路径被访问", service_name="fastapi-demo", endpoint="/")
    return {"message": "Hello World"}

@app.get("/error")
async def error_endpoint():
    logger.error("模拟错误", service_name="fastapi-demo", endpoint="/error", error_type="demo")
    raise Exception("这是一个示例错误")

@app.get("/trace/{item_id}")
async def trace_example(item_id: str):
    with tracer.start_as_current_span("process_item") as span:
        span.set_attribute("item.id", item_id)
        logger.info("处理项目", service_name="fastapi-demo", item_id=item_id)
        
        # 模拟一些处理
        import time
        time.sleep(0.1)
        
        logger.info("项目处理完成", service_name="fastapi-demo", item_id=item_id)
        return {"item_id": item_id, "status": "processed"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. Docker Compose 集成

```yaml
# 在您的 FastAPI 项目中，添加到 docker-compose.yml
services:
  fastapi-app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs  # 重要：日志目录映射
    environment:
      - SERVICE_NAME=fastapi-demo
```

### 4. 日志目录结构

确保您的应用日志写入到 `./logs/` 目录：

```
logs/
├── app.log          # 主应用日志
├── error.log        # 错误日志（可选）
└── access.log       # 访问日志（可选）
```

## 📊 Grafana 查询示例

### 常用 LogQL 查询

1. **查看所有 FastAPI 日志**:
   ```
   {job="fastapi"}
   ```

2. **筛选错误日志**:
   ```
   {job="fastapi", level="ERROR"}
   ```

3. **按服务名筛选**:
   ```
   {job="fastapi", service_name="fastapi-demo"}
   ```

4. **查找包含特定 trace_id 的日志**:
   ```
   {job="fastapi"} |~ "trace_id.*abc123"
   ```

5. **统计错误数量**:
   ```
   sum(count_over_time({job="fastapi", level="ERROR"} [5m]))
   ```

## 🛠️ 管理命令

使用 `manage.sh` 脚本管理平台：

```bash
# 启动服务
./manage.sh start

# 停止服务
./manage.sh stop

# 重启服务
./manage.sh restart

# 查看状态
./manage.sh status

# 查看日志
./manage.sh logs              # 所有服务日志
./manage.sh logs grafana      # Grafana 日志
./manage.sh logs loki         # Loki 日志
./manage.sh logs promtail     # Promtail 日志

# 清理数据
./manage.sh clean
```

## 🔍 故障排除

### 常见问题

1. **日志没有出现在 Grafana 中**
   - 检查日志文件是否存在于 `./logs/` 目录
   - 确认日志格式为 JSON
   - 检查 Promtail 日志: `./manage.sh logs promtail`

2. **Grafana 无法连接到 Loki**
   - 确认所有服务都在运行: `./manage.sh status`
   - 检查网络配置

3. **OpenTelemetry trace 信息缺失**
   - 确认已正确配置 structlog 处理器
   - 检查 trace 上下文是否正确传播

### 调试步骤

1. 检查服务状态:
   ```bash
   ./manage.sh status
   ```

2. 查看特定服务日志:
   ```bash
   ./manage.sh logs loki
   ./manage.sh logs promtail
   ```

3. 测试 Loki API:
   ```bash
   curl -G -s "http://localhost:3101/loki/api/v1/label"
   ```

## 🔄 OpenTelemetry 最佳实践

1. **结构化日志**: 使用 JSON 格式，包含 trace_id 和 span_id
2. **统一标签**: 为所有日志添加 service_name 标签
3. **错误处理**: 确保异常信息被正确记录
4. **性能监控**: 结合 traces 和 logs 进行完整的可观测性

## 📈 日志采集数据流程详解

### 完整的数据流程架构

我们的日志观测平台采用现代化的日志采集架构，实现了从应用产生日志到最终可视化展示的完整数据流程：

```
FastAPI 应用 → 文件存储 → Promtail 收集 → Loki 存储 → Grafana 展示
```

### 阶段一：FastAPI 应用日志生成

**技术实现**：
- 使用 **structlog** 库实现结构化 JSON 日志
- 集成 **OpenTelemetry** 自动注入 trace_id 和 span_id
- 支持多级别日志（INFO, WARN, ERROR, DEBUG）

**日志格式示例**：
```json
{
  "timestamp": "2024-11-14T14:16:54.123Z",
  "level": "info",
  "logger_name": "uvicorn.access",
  "message": "GET /api/health 200",
  "service_name": "aichemol-backend",
  "trace_id": "abc123def456789",
  "span_id": "def456789abc",
  "method": "GET",
  "endpoint": "/api/health",
  "status_code": 200
}
```

**配置关键点**：
```python
# 结构化日志配置
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_trace_info,  # 添加 OpenTelemetry trace 信息
        structlog.processors.JSONRenderer()
    ]
)
```

### 阶段二：文件系统存储

**存储机制**：
- 应用将日志写入 `/app/logs/` 目录
- Docker 容器通过 volume mounting 映射到宿主机
- 支持日志文件轮转和压缩

**Docker 卷映射配置**：
```yaml
services:
  backend:
    volumes:
      - /home/songyou/meiyue/backend-aichemol/logs:/app/logs
  promtail:
    volumes:
      - /home/songyou/meiyue/backend-aichemol/logs:/app/logs:ro
```

### 阶段三：Promtail 日志收集

**收集策略**：
- 监控指定目录下的 `.log` 文件
- 实时读取新增日志内容
- 解析 JSON 格式并提取标签

**Promtail 配置核心**：
```yaml
scrape_configs:
  - job_name: aichemol_backend
    static_configs:
      - targets:
          - localhost
        labels:
          job: aichemol_backend
          service: backend
          __path__: /app/logs/*.log
    
    pipeline_stages:
      - json:
          expressions:
            level: level
            service_name: service_name
            trace_id: trace_id
            timestamp: timestamp
      
      - timestamp:
          source: timestamp
          format: RFC3339Nano
      
      - labels:
          level:
          service_name:
          trace_id:
```

**标签提取功能**：
- 自动从 JSON 日志中提取关键字段作为 Loki 标签
- 支持动态标签（如 service_name, level, trace_id）
- 便于后续在 Grafana 中进行精确查询和过滤

### 阶段四：Loki 日志存储

**存储架构**：
- **标签索引**：基于提取的标签创建高效索引
- **时序存储**：按时间顺序存储日志内容
- **压缩存储**：自动压缩历史日志数据

**Loki 配置要点**：
```yaml
ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 1h
  max_chunk_age: 1h
  chunk_target_size: 1048576
  chunk_retain_period: 30s

limits_config:
  creation_grace_period: 10m  # 处理时区差异
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
```

**数据保留策略**：
- 支持按时间自动清理历史数据
- 可配置不同级别日志的保留期限
- 压缩存储节省磁盘空间

### 阶段五：Grafana 可视化展示

**查询引擎**：
- 使用 **LogQL** 查询语言
- 支持正则表达式和复杂过滤条件
- 实时和历史数据查询

**常用查询示例**：

1. **查看特定服务日志**：
```logql
{job="aichemol_backend", service_name="aichemol-backend"}
```

2. **错误日志监控**：
```logql
{job="aichemol_backend", level="ERROR"}
```

3. **按 Trace ID 跟踪请求**：
```logql
{job="aichemol_backend"} |~ "trace_id.*abc123"
```

4. **日志数量统计**：
```logql
sum(count_over_time({job="aichemol_backend"}[5m])) by (level)
```

**仪表板功能**：
- 实时日志流展示
- 日志级别分布图表
- 错误率趋势监控
- 服务健康状态监控

### 阶段六：监控告警

**告警配置**：
```yaml
# Grafana 告警规则示例
rules:
  - alert: HighErrorRate
    expr: |
      sum(rate({job="aichemol_backend", level="ERROR"}[5m])) 
      / 
      sum(rate({job="aichemol_backend"}[5m])) > 0.1
    for: 5m
    annotations:
      summary: "错误率过高"
      description: "服务 {{ $labels.service_name }} 错误率超过 10%"
```

### 性能优化建议

**日志级别管理**：
```python
# 生产环境建议配置
LOGGING_LEVELS = {
    "production": "WARNING",
    "staging": "INFO", 
    "development": "DEBUG"
}
```

**标签优化**：
- 控制标签数量（建议 < 10 个）
- 避免高基数标签（如用户ID、请求ID）
- 使用静态标签提高查询性能

**存储优化**：
- 配置合理的日志保留期
- 使用日志采样减少存储压力
- 定期清理无用日志文件

## 🔧 故障排除指南

### 日志流程诊断

**步骤一：检查应用日志生成**
```bash
# 检查应用是否正常生成日志
ls -la /home/songyou/meiyue/backend-aichemol/logs/
tail -f /home/songyou/meiyue/backend-aichemol/logs/app.log
```

**步骤二：验证 Promtail 收集**
```bash
# 查看 Promtail 状态和日志
docker logs dev_ops_promtail_1
curl http://localhost:9080/targets  # Promtail targets API
```

**步骤三：确认 Loki 存储**
```bash
# 测试 Loki API
curl -G -s "http://localhost:3101/loki/api/v1/label"
curl -G -s "http://localhost:3101/loki/api/v1/query_range" \
  --data-urlencode 'query={job="aichemol_backend"}' \
  --data-urlencode 'start=1699000000000000000' \
  --data-urlencode 'end=1699999999000000000'
```

**步骤四：验证 Grafana 展示**
```bash
# 检查 Grafana 数据源连接
curl -u admin:admin123 http://localhost:3100/api/datasources
```

### 常见问题解决

**问题一：日志时间戳被拒绝**
```
error: entry timestamp too new
```
解决方案：在 Loki 配置中增加时间容忍度
```yaml
limits_config:
  creation_grace_period: 10m
```

**问题二：Docker 卷映射路径不匹配**
```
error: no such file or directory
```
解决方案：确保路径一致
```yaml
# Docker Compose 中确保路径匹配
volumes:
  - /host/path/logs:/container/path/logs
```

**问题三：JSON 解析失败**
```
error: failed to parse JSON
```
解决方案：检查日志格式和 Promtail 配置
```yaml
pipeline_stages:
  - json:
      expressions:
        timestamp: timestamp
        level: level
        message: message
```

## 🚀 扩展功能

- 添加告警规则和通知渠道
- 集成 Prometheus 指标监控
- 配置多环境日志隔离
- 实现日志数据备份和恢复
- 添加自定义仪表板模板
- 集成日志异常检测算法
- 支持日志全文搜索功能

## 📝 许可证

MIT License