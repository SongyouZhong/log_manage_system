# 多应用 OpenTelemetry 集成配置示例

本目录包含了配置多个应用通过 OpenTelemetry 直接发送遥测数据到观测平台的示例。

## 🏗️ 架构说明

```
多个 Python 应用     ┐
(FastAPI, Django,    ├── OpenTelemetry OTLP ──→ OTel Collector ──→ Loki ──→ Grafana
 Flask, etc.)        ┘
```

## 🔌 接收端点

你的 OpenTelemetry Collector 提供以下接收端点：

| 协议 | 端口 | 端点 | 用途 | 推荐度 |
|------|------|------|------|--------|
| **OTLP gRPC** | **4317** | - | **推荐的 OpenTelemetry 协议** | ⭐⭐⭐⭐⭐ |
| **OTLP HTTP** | **4318** | /v1/traces, /v1/logs, /v1/metrics | **HTTP 版本的 OTLP** | ⭐⭐⭐⭐ |
| Jaeger gRPC | 14250 | - | 兼容 Jaeger | ⭐⭐⭐ |
| Jaeger HTTP | 14268 | /api/traces | 兼容 Jaeger HTTP | ⭐⭐⭐ |
| Zipkin | 9411 | /api/v2/spans | 兼容 Zipkin | ⭐⭐ |

> 💡 **建议**: 新项目优先使用 OTLP gRPC (端口 4317)，性能最佳且功能最完整。

## 📋 Python 应用配置示例

### 方式一：完整配置示例 (推荐)

```python
import os
import logging
from datetime import datetime
from opentelemetry import trace, _logs
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
import structlog

# 配置资源信息 - 标识你的应用
resource = Resource.create({
    "service.name": "your-app-name",        # 🔧 替换为你的应用名
    "service.version": "1.0.0",             # 应用版本
    "deployment.environment": "production",  # 环境标识 (dev/staging/production)
    "service.instance.id": os.getenv("HOSTNAME", "local-instance"),
})

# 🚀 配置 OpenTelemetry Traces
trace_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(trace_provider)

# OTLP Exporter 配置 - 发送到你的观测平台
OTEL_COLLECTOR_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

otlp_span_exporter = OTLPSpanExporter(
    endpoint=OTEL_COLLECTOR_ENDPOINT,  # 🔧 替换为你的服务器地址
    insecure=True,
    compression=None,
)

trace_provider.add_span_processor(
    BatchSpanProcessor(
        otlp_span_exporter,
        max_queue_size=512,
        max_export_batch_size=128,
        export_timeout_millis=30000,
    )
)

# 🚀 配置 OpenTelemetry Logs
logger_provider = LoggerProvider(resource=resource)
_logs.set_logger_provider(logger_provider)

otlp_log_exporter = OTLPLogExporter(
    endpoint=OTEL_COLLECTOR_ENDPOINT,  # 🔧 替换为你的服务器地址
    insecure=True,
)

logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(
        otlp_log_exporter,
        max_queue_size=512,
        max_export_batch_size=128,
        export_timeout_millis=30000,
    )
)

# 配置结构化日志与 OpenTelemetry 集成
def add_otel_context(logger, method_name, event_dict):
    """添加 OpenTelemetry trace 上下文到日志"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span_context = span.get_span_context()
        if span_context.trace_id != 0:
            event_dict["trace_id"] = format(span_context.trace_id, "032x")
            event_dict["span_id"] = format(span_context.span_id, "016x")
            event_dict["trace_flags"] = span_context.trace_flags
    return event_dict

def add_service_context(logger, method_name, event_dict):
    """添加服务上下文信息"""
    event_dict.update({
        "service_name": "your-app-name",  # 🔧 替换为你的应用名
        "service_version": "1.0.0",
        "environment": "production",
    })
    return event_dict

# 配置 structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        add_service_context,
        add_otel_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# 获取 logger 和 tracer
logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

# FastAPI 应用示例
from fastapi import FastAPI

app = FastAPI(title="OpenTelemetry 集成应用")

# 自动 instrumentation
FastAPIInstrumentor.instrument_app(app)
LoggingInstrumentor().instrument()

# 使用示例
@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    with tracer.start_as_current_span("get_user") as span:
        # 设置 span 属性
        span.set_attribute("user.id", user_id)
        span.set_attribute("operation.type", "user_lookup")
        
        # 记录结构化日志
        logger.info("获取用户信息", 
            user_id=user_id,
            endpoint="/api/users/{user_id}",
            method="GET"
        )
        
        # 模拟业务逻辑
        user_data = {"id": user_id, "name": f"User {user_id}"}
        
        # 记录结果
        span.set_attribute("result.found", True)
        logger.info("用户信息获取成功", 
            user_id=user_id,
            found=True
        )
        
        return user_data

@app.post("/api/orders")
async def create_order(order_data: dict):
    with tracer.start_as_current_span("create_order") as span:
        order_id = order_data.get("id", "unknown")
        span.set_attribute("order.id", order_id)
        span.set_attribute("operation.type", "order_creation")
        
        logger.info("创建订单", 
            order_id=order_id,
            order_data=order_data,
            endpoint="/api/orders",
            method="POST"
        )
        
        # 嵌套 span 示例
        with tracer.start_as_current_span("validate_order"):
            logger.info("验证订单", order_id=order_id)
            # 验证逻辑...
        
        with tracer.start_as_current_span("save_order"):
            logger.info("保存订单", order_id=order_id)
            # 保存逻辑...
        
        logger.info("订单创建成功", 
            order_id=order_id,
            processing_status="completed"
        )
        
        return {"order_id": order_id, "status": "created"}
```

### 方式二：环境变量配置 (简化方式)

```python
# 设置环境变量 (推荐在容器或系统级别设置)
import os
os.environ.setdefault("OTEL_SERVICE_NAME", "your-app-name")
os.environ.setdefault("OTEL_SERVICE_VERSION", "1.0.0")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", "deployment.environment=production")

# 使用自动配置
from opentelemetry.auto_instrumentation import sitecustomize
from opentelemetry import trace
import structlog

# 获取自动配置的 tracer
tracer = trace.get_tracer(__name__)

# 配置 structlog (简化版)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger(__name__)

# 应用代码保持不变...
```

## 🚀 快速开始

### 1. 启动观测平台

```bash
# 在项目根目录启动完整观测平台
cd /path/to/dev_ops
./manage.sh start

# 验证所有服务运行正常
./manage.sh status

# 检查 OpenTelemetry Collector 健康状态
curl http://localhost:13133/
```

平台服务地址：
- **Grafana**: http://localhost:3100 (admin/admin123)
- **Loki API**: http://localhost:3101  
- **OpenTelemetry Collector Health**: http://localhost:13133
- **OTel Collector Metrics**: http://localhost:8888/metrics

### 2. 安装 Python 依赖

```bash
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-otlp-proto-grpc
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-logging  
pip install structlog
```

### 3. 配置你的应用

在应用启动前设置环境变量：

```bash
# 基础服务配置
export OTEL_SERVICE_NAME="your-app-name"
export OTEL_SERVICE_VERSION="1.0.0"
export OTEL_RESOURCE_ATTRIBUTES="deployment.environment=production,team=backend"

# OpenTelemetry Collector 端点配置 (推荐使用 gRPC)
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://localhost:4317"
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT="http://localhost:4317"

# 或者使用 HTTP 协议
# export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
# export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
```

### 4. 运行示例应用

```bash
# 进入示例目录
cd examples/multi-app-integration

# 安装依赖
pip install -r requirements.txt

# 启动示例应用
python main.py
```

### 5. 生成测试数据

```bash
# 运行测试脚本生成示例数据
chmod +x test.sh
./test.sh
```

## 📊 在 Grafana 中查看数据

### 1. 访问 Grafana 界面

- 打开浏览器访问: http://localhost:3100
- 用户名: `admin`
- 密码: `admin123`

### 2. 基本查询语句

**查看所有应用的日志**:
```logql
{service_name=~".+"}
```

**查看特定服务的日志**:
```logql
{service_name="your-app-name"}
```

**查看错误日志**:
```logql
{service_name=~".+"} | json | level="error"
```

**追踪特定请求链路**:
```logql
{service_name=~".+"} | json | trace_id="your_trace_id"
```

**统计错误频率**:
```logql
rate({service_name=~".+"} | json | level="error"[5m])
```

**查看特定端点的日志**:
```logql
{service_name="your-app-name"} | json | endpoint="/api/users"
```

### 3. 高级查询示例

**按时间范围查看慢请求**:
```logql
{service_name=~".+"} | json | duration > 1000
```

**查看用户操作轨迹**:
```logql
{service_name=~".+"} | json | user_id="specific_user"
```

**服务间调用链分析**:
```logql
{service_name=~".+"} | json | trace_id=~".+" | sort by timestamp desc
```

## 🔧 进阶配置

### 自定义采样策略

在你的应用中配置采样率：

```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

# 配置 10% 采样率
sampler = TraceIdRatioBased(0.1)
trace_provider = TracerProvider(resource=resource, sampler=sampler)
```

### 性能优化配置

```python
# 优化批处理配置
trace_provider.add_span_processor(
    BatchSpanProcessor(
        otlp_span_exporter,
        max_queue_size=2048,        # 增加队列大小
        max_export_batch_size=512,  # 增加批处理大小
        export_timeout_millis=30000, # 导出超时
        schedule_delay_millis=5000,  # 调度延迟
    )
)
```

### 添加自定义属性

```python
# 在应用级别添加全局属性
resource = Resource.create({
    "service.name": "your-app-name",
    "service.version": "1.0.0",
    "deployment.environment": "production",
    # 自定义属性
    "team": "backend",
    "datacenter": "us-west-1",
    "kubernetes.pod.name": os.getenv("HOSTNAME"),
    "custom.build_id": os.getenv("BUILD_ID", "unknown"),
})

# 在 span 级别添加动态属性
@app.middleware("http")
async def add_custom_attributes(request, call_next):
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("http.request_id", str(uuid.uuid4()))
        span.set_attribute("http.user_agent", request.headers.get("user-agent"))
        span.set_attribute("http.client_ip", request.client.host)
    
    response = await call_next(request)
    return response
```

### 错误和异常处理

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    span = trace.get_current_span()
    if span.is_recording():
        # 记录异常信息到 span
        span.record_exception(exc)
        span.set_status(trace.Status(trace.StatusCode.ERROR))
        span.set_attribute("error.type", type(exc).__name__)
        span.set_attribute("error.message", str(exc))
    
    # 记录结构化错误日志
    logger.error("未处理的异常",
        error_type=type(exc).__name__,
        error_message=str(exc),
        request_url=str(request.url),
        request_method=request.method,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
```

## 🔍 故障排除

### 常见问题及解决方案

#### 1. 数据未出现在 Grafana

**检查步骤**:
```bash
# 1. 验证 OpenTelemetry Collector 运行状态
curl http://localhost:13133/

# 2. 检查 Collector 日志
sudo docker logs otel-collector

# 3. 验证应用连接
# 在应用中添加调试日志确认数据发送
logger.info("OpenTelemetry initialized", 
    collector_endpoint=OTEL_COLLECTOR_ENDPOINT,
    service_name="your-app-name"
)

# 4. 检查 Loki 是否接收到数据
curl -G -s "http://localhost:3101/loki/api/v1/labels"
```

**常见原因**:
- 🔧 服务器地址配置错误：检查 `OTEL_EXPORTER_OTLP_ENDPOINT`
- 🔧 网络连接问题：确认防火墙和网络配置
- 🔧 数据格式错误：确认使用正确的 exporter 配置

#### 2. 连接被拒绝 (Connection Refused)

```bash
# 检查端口是否开放
netstat -tulpn | grep :4317
netstat -tulpn | grep :4318

# 检查 Docker 容器端口映射
sudo docker ps | grep otel-collector

# 测试端点连通性
telnet localhost 4317
```

#### 3. 性能影响过大

```python
# 1. 降低采样率
sampler = TraceIdRatioBased(0.01)  # 1% 采样

# 2. 优化批处理
BatchSpanProcessor(
    exporter,
    max_queue_size=512,          # 减少队列大小
    max_export_batch_size=128,   # 减少批次大小
    schedule_delay_millis=1000,  # 减少延迟
)

# 3. 异步导出 (默认已启用)
# BatchSpanProcessor 已经是异步的

# 4. 过滤敏感数据
def filter_sensitive_attributes(logger, method_name, event_dict):
    # 移除敏感信息
    if 'password' in event_dict:
        event_dict['password'] = '[REDACTED]'
    return event_dict
```

#### 4. Trace 信息不完整

```python
# 确保正确的上下文传播
from opentelemetry.propagate import inject, extract

# 在发起外部请求时注入上下文
headers = {}
inject(headers)
response = requests.get("http://external-api", headers=headers)

# 在接收请求时提取上下文  
@app.middleware("http")
async def trace_middleware(request, call_next):
    # 从请求头提取 trace 上下文
    parent_ctx = extract(dict(request.headers))
    
    with tracer.start_as_current_span("http_request", context=parent_ctx):
        response = await call_next(request)
        return response
```

### 调试工具

#### 开启详细日志

```python
import logging

# OpenTelemetry 调试日志
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
logging.getLogger("opentelemetry.exporter.otlp").setLevel(logging.DEBUG)

# 应用调试日志
logger.info("Debug info", 
    trace_enabled=trace.get_tracer_provider() is not None,
    current_span_id=format(trace.get_current_span().get_span_context().span_id, "016x") if trace.get_current_span().is_recording() else "none"
)
```

#### 本地测试脚本

```python
# test_otel_connection.py
import requests
from opentelemetry.test_utils import TraceTestCase

def test_otel_collector():
    """测试 OpenTelemetry Collector 连接"""
    try:
        # 测试健康检查
        health_response = requests.get("http://localhost:13133/")
        print(f"Health check: {health_response.status_code}")
        
        # 测试 HTTP 端点
        test_data = {"resourceSpans": []}
        trace_response = requests.post(
            "http://localhost:4318/v1/traces",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"OTLP HTTP endpoint: {trace_response.status_code}")
        
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_otel_collector()
```

## 🚀 生产环境最佳实践

### 1. 安全配置

```python
# 生产环境应使用 TLS
otlp_span_exporter = OTLPSpanExporter(
    endpoint="https://your-production-server:4317",
    insecure=False,  # 启用 TLS
    credentials=grpc.ssl_channel_credentials(),
    headers=[("authorization", f"Bearer {api_token}")],
)
```

### 2. 资源限制

```python
# 限制内存使用
trace_provider.add_span_processor(
    BatchSpanProcessor(
        exporter,
        max_queue_size=1024,         # 限制队列大小
        max_export_batch_size=256,   # 限制批次大小
        export_timeout_millis=10000, # 缩短超时时间
    )
)
```

### 3. 监控配置

```python
# 添加自定义指标
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider

meter = metrics.get_meter(__name__)
request_counter = meter.create_counter(
    "http_requests_total",
    description="Total HTTP requests"
)

@app.middleware("http") 
async def metrics_middleware(request, call_next):
    request_counter.add(1, {"method": request.method, "endpoint": request.url.path})
    response = await call_next(request)
    return response
```

### 4. 配置管理

```python
# 使用配置文件管理
from dataclasses import dataclass
from typing import Optional

@dataclass
class OTelConfig:
    service_name: str
    service_version: str
    environment: str
    collector_endpoint: str
    sampling_rate: float = 1.0
    enable_logging: bool = True
    enable_tracing: bool = True
    
    @classmethod
    def from_env(cls) -> 'OTelConfig':
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "unknown"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "unknown"),
            environment=os.getenv("OTEL_ENVIRONMENT", "production"),
            collector_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            sampling_rate=float(os.getenv("OTEL_SAMPLING_RATE", "1.0")),
            enable_logging=os.getenv("OTEL_ENABLE_LOGGING", "true").lower() == "true",
            enable_tracing=os.getenv("OTEL_ENABLE_TRACING", "true").lower() == "true",
        )

# 使用配置
config = OTelConfig.from_env()
if config.enable_tracing:
    setup_tracing(config)
if config.enable_logging:
    setup_logging(config)
```