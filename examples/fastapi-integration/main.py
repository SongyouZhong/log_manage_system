import logging
import structlog
import sys
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

# OpenTelemetry 配置
resource = Resource.create({"service.name": "fastapi-demo"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# 配置结构化日志
def add_trace_info(logger, method_name, event_dict):
    """添加 trace 信息到日志中"""
    span = trace.get_current_span()
    if span:
        span_context = span.get_span_context()
        if span_context.trace_id != 0:  # 检查是否有有效的 trace
            event_dict["trace_id"] = format(span_context.trace_id, "032x")
            event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict

def add_service_info(logger, method_name, event_dict):
    """添加服务信息"""
    event_dict["service_name"] = "fastapi-demo"
    return event_dict

# 配置 structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        add_service_info,
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

# 确保日志目录存在
import os
log_dir = "../../logs"
os.makedirs(log_dir, exist_ok=True)

# 配置日志输出到文件
file_handler = logging.FileHandler(f'{log_dir}/app.log')
file_handler.setFormatter(logging.Formatter('%(message)s'))

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(logging.StreamHandler(sys.stdout))

logger = structlog.get_logger()

# 创建 FastAPI 应用
app = FastAPI(
    title="FastAPI OpenTelemetry 示例",
    description="展示 FastAPI + OpenTelemetry + 结构化日志集成",
    version="1.0.0"
)

# 自动 instrument FastAPI
FastAPIInstrumentor.instrument_app(app)
LoggingInstrumentor().instrument()

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI 应用启动", event="app_startup")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI 应用关闭", event="app_shutdown")

@app.get("/")
async def root():
    logger.info("根路径被访问", endpoint="/", method="GET")
    return {
        "message": "Hello World", 
        "service": "fastapi-demo",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    logger.info("健康检查", endpoint="/health", method="GET")
    return {"status": "healthy", "service": "fastapi-demo"}

@app.get("/error")
async def error_endpoint():
    logger.error("模拟错误端点被调用", endpoint="/error", error_type="demo")
    try:
        # 故意制造一个错误
        result = 1 / 0
    except Exception as e:
        logger.error(
            "捕获到异常", 
            endpoint="/error",
            error_type="ZeroDivisionError",
            error_message=str(e),
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="这是一个示例错误")

@app.get("/trace/{item_id}")
async def trace_example(item_id: str):
    with tracer.start_as_current_span("process_item") as span:
        span.set_attribute("item.id", item_id)
        span.set_attribute("operation", "trace_example")
        
        logger.info("开始处理项目", endpoint="/trace", item_id=item_id, operation="start")
        
        # 模拟一些处理时间
        time.sleep(0.1)
        
        # 添加嵌套 span
        with tracer.start_as_current_span("validate_item") as validation_span:
            validation_span.set_attribute("validation.type", "basic")
            logger.info("验证项目", item_id=item_id, operation="validate")
            time.sleep(0.05)
        
        with tracer.start_as_current_span("process_business_logic") as business_span:
            business_span.set_attribute("business.type", "demo")
            logger.info("执行业务逻辑", item_id=item_id, operation="business_logic")
            time.sleep(0.05)
        
        logger.info("项目处理完成", endpoint="/trace", item_id=item_id, operation="complete")
        
        return {
            "item_id": item_id, 
            "status": "processed",
            "trace_id": format(span.get_span_context().trace_id, "032x"),
            "span_id": format(span.get_span_context().span_id, "016x")
        }

@app.get("/metrics")
async def metrics_example():
    """演示不同日志级别和结构化数据"""
    logger.debug("调试信息", endpoint="/metrics", level="debug")
    logger.info("信息级别日志", endpoint="/metrics", level="info", user_count=42)
    logger.warning("警告信息", endpoint="/metrics", level="warning", memory_usage="85%")
    
    return {
        "message": "已记录不同级别的日志",
        "levels": ["debug", "info", "warning"]
    }

@app.post("/user/{user_id}/action")
async def user_action(user_id: str, action: dict):
    """演示 POST 请求的日志记录"""
    with tracer.start_as_current_span("user_action") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("action.type", action.get("type", "unknown"))
        
        logger.info(
            "用户执行操作",
            endpoint="/user/{user_id}/action",
            user_id=user_id,
            action_type=action.get("type"),
            action_data=action
        )
        
        # 模拟处理
        time.sleep(0.2)
        
        result = {
            "user_id": user_id,
            "action": action,
            "status": "completed",
            "processed_at": datetime.now().isoformat()
        }
        
        logger.info(
            "用户操作处理完成",
            user_id=user_id,
            action_type=action.get("type"),
            result=result
        )
        
        return result

if __name__ == "__main__":
    import uvicorn
    logger.info("启动 FastAPI 服务器", host="0.0.0.0", port=8000)
    uvicorn.run(app, host="0.0.0.0", port=8000)