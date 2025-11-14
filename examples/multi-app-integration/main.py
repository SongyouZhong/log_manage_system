"""
示例：多应用 OpenTelemetry 集成
展示如何通过 OTLP 协议发送遥测数据到观测平台
"""
import os
import time
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
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
from opentelemetry.propagate import inject, extract
import structlog

# 配置资源信息
resource = Resource.create({
    "service.name": "multi-app-demo",
    "service.version": "1.0.0", 
    "deployment.environment": "development",
    "service.instance.id": os.getenv("HOSTNAME", "local-instance"),
})

# 配置 OpenTelemetry Traces
trace_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(trace_provider)

# OTLP Exporter 配置 - 发送到 OpenTelemetry Collector
# 注意：替换 localhost 为你的服务器地址
OTEL_COLLECTOR_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

otlp_span_exporter = OTLPSpanExporter(
    endpoint=OTEL_COLLECTOR_ENDPOINT,
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

# 配置 OpenTelemetry Logs
logger_provider = LoggerProvider(resource=resource)
_logs.set_logger_provider(logger_provider)

otlp_log_exporter = OTLPLogExporter(
    endpoint=OTEL_COLLECTOR_ENDPOINT,
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

# 配置 structlog 与 OpenTelemetry 集成
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
        "service_name": "multi-app-demo",
        "service_version": "1.0.0",
        "environment": "development",
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

# 配置标准日志库
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler()]
)

# 获取 logger 和 tracer
logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="多应用 OpenTelemetry 集成示例",
    description="展示如何通过 OTLP 发送遥测数据到观测平台",
    version="1.0.0"
)

# 自动 instrumentation
FastAPIInstrumentor.instrument_app(app)
LoggingInstrumentor().instrument()

# 模拟数据库操作
@tracer.start_as_current_span
def simulate_db_query(query_type: str, entity_id: str):
    """模拟数据库查询"""
    span = trace.get_current_span()
    span.set_attribute("db.operation", query_type)
    span.set_attribute("db.entity.id", entity_id)
    
    logger.info("执行数据库查询", 
        db_operation=query_type, 
        entity_id=entity_id,
        query_duration_hint="simulated"
    )
    
    # 模拟查询时间
    time.sleep(0.05 + (hash(entity_id) % 50) / 1000)
    
    if query_type == "select":
        result_count = (hash(entity_id) % 10) + 1
        span.set_attribute("db.result.count", result_count)
        logger.info("数据库查询完成", 
            result_count=result_count,
            query_success=True
        )
        return {"count": result_count, "data": f"mock_data_for_{entity_id}"}
    
    logger.info("数据库操作完成", operation_success=True)
    return {"success": True}

# 模拟外部服务调用
@tracer.start_as_current_span
def call_external_service(service_name: str, operation: str):
    """模拟外部服务调用"""
    span = trace.get_current_span()
    span.set_attribute("external.service.name", service_name)
    span.set_attribute("external.operation", operation)
    
    logger.info("调用外部服务", 
        external_service=service_name,
        operation=operation,
        call_start=datetime.now().isoformat()
    )
    
    # 模拟网络延迟
    time.sleep(0.1 + (hash(service_name + operation) % 100) / 1000)
    
    # 模拟偶发错误
    if hash(service_name + operation) % 10 == 0:
        span.record_exception(Exception(f"{service_name} service temporarily unavailable"))
        span.set_status(trace.Status(trace.StatusCode.ERROR))
        logger.error("外部服务调用失败", 
            external_service=service_name,
            operation=operation,
            error_type="service_unavailable"
        )
        raise HTTPException(status_code=503, detail=f"{service_name} service unavailable")
    
    logger.info("外部服务调用成功", 
        external_service=service_name,
        operation=operation,
        response_status="success"
    )
    return {"service": service_name, "result": f"{operation}_completed"}

# API 端点
@app.on_event("startup")
async def startup_event():
    logger.info("应用启动", 
        service_name="multi-app-demo",
        startup_time=datetime.now().isoformat(),
        otel_endpoint=OTEL_COLLECTOR_ENDPOINT
    )

@app.on_event("shutdown") 
async def shutdown_event():
    logger.info("应用关闭", 
        service_name="multi-app-demo",
        shutdown_time=datetime.now().isoformat()
    )

@app.get("/")
async def root():
    """基础健康检查端点"""
    with tracer.start_as_current_span("health_check") as span:
        span.set_attribute("endpoint", "/")
        span.set_attribute("operation.type", "health_check")
        
        logger.info("健康检查请求", endpoint="/", method="GET")
        
        return {
            "service": "multi-app-demo",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }

@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    """获取用户信息 - 演示数据库查询追踪"""
    with tracer.start_as_current_span("get_user") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("operation.type", "user_lookup")
        
        logger.info("获取用户信息请求", 
            user_id=user_id,
            endpoint="/api/users/{user_id}",
            method="GET"
        )
        
        # 模拟数据库查询
        user_data = simulate_db_query("select", user_id)
        
        # 模拟调用用户权限服务
        permissions = call_external_service("user-permissions", "get_permissions")
        
        result = {
            "user_id": user_id,
            "data": user_data,
            "permissions": permissions,
            "retrieved_at": datetime.now().isoformat()
        }
        
        logger.info("用户信息获取成功", 
            user_id=user_id,
            data_fields_count=len(user_data),
            permissions_count=1
        )
        
        return result

@app.post("/api/users/{user_id}/actions")
async def user_action(user_id: str, action_data: dict):
    """用户操作 - 演示复杂业务流程追踪"""
    with tracer.start_as_current_span("user_action") as span:
        action_type = action_data.get("type", "unknown")
        span.set_attribute("user.id", user_id)
        span.set_attribute("action.type", action_type)
        span.set_attribute("operation.type", "user_action")
        
        logger.info("用户操作请求", 
            user_id=user_id,
            action_type=action_type,
            action_data=action_data,
            endpoint="/api/users/{user_id}/actions",
            method="POST"
        )
        
        # 验证用户权限
        with tracer.start_as_current_span("validate_permissions"):
            permissions = call_external_service("user-permissions", "validate_action")
            logger.info("权限验证完成", user_id=user_id, action_type=action_type)
        
        # 执行业务操作
        with tracer.start_as_current_span("execute_business_logic"):
            if action_type == "purchase":
                # 模拟支付处理
                payment_result = call_external_service("payment-service", "process_payment")
                logger.info("支付处理完成", user_id=user_id, payment_status="success")
                
                # 更新用户记录
                update_result = simulate_db_query("update", user_id)
                logger.info("用户记录更新完成", user_id=user_id)
                
            elif action_type == "login":
                # 记录登录事件
                login_result = simulate_db_query("insert", f"login_{user_id}")
                logger.info("登录事件记录完成", user_id=user_id)
                
            else:
                logger.warning("未知操作类型", 
                    user_id=user_id,
                    action_type=action_type,
                    action_data=action_data
                )
        
        # 发送通知
        with tracer.start_as_current_span("send_notification"):
            notification_result = call_external_service("notification-service", "send_notification")
            logger.info("通知发送完成", user_id=user_id, action_type=action_type)
        
        result = {
            "user_id": user_id,
            "action": action_data,
            "status": "completed",
            "processed_at": datetime.now().isoformat(),
            "trace_id": format(span.get_span_context().trace_id, "032x")
        }
        
        logger.info("用户操作处理完成", 
            user_id=user_id,
            action_type=action_type,
            processing_status="success",
            trace_id=format(span.get_span_context().trace_id, "032x")
        )
        
        return result

@app.get("/api/error-demo")
async def error_demo():
    """错误演示端点 - 展示错误追踪"""
    with tracer.start_as_current_span("error_demo") as span:
        span.set_attribute("operation.type", "error_simulation")
        
        logger.info("错误演示请求", endpoint="/api/error-demo")
        
        try:
            # 模拟业务错误
            if datetime.now().second % 2 == 0:
                raise ValueError("模拟的业务逻辑错误")
            else:
                # 模拟外部服务错误
                call_external_service("unstable-service", "risky_operation")
                
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            
            logger.error("操作执行失败", 
                error_type=type(e).__name__,
                error_message=str(e),
                endpoint="/api/error-demo",
                exc_info=True
            )
            
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics-demo")
async def metrics_demo():
    """指标演示端点 - 展示结构化日志记录"""
    with tracer.start_as_current_span("metrics_demo") as span:
        span.set_attribute("operation.type", "metrics_collection")
        
        logger.info("指标收集演示", endpoint="/api/metrics-demo")
        
        # 模拟不同级别的日志
        logger.debug("调试信息", 
            endpoint="/api/metrics-demo",
            debug_info="detailed_processing_info"
        )
        
        logger.info("处理开始", 
            operation="metrics_collection",
            start_time=datetime.now().isoformat()
        )
        
        # 模拟一些处理
        time.sleep(0.2)
        
        logger.info("处理进行中", 
            progress=50,
            estimated_remaining_time="5s"
        )
        
        time.sleep(0.1)
        
        logger.info("处理完成", 
            operation="metrics_collection",
            end_time=datetime.now().isoformat(),
            processing_time="0.3s",
            records_processed=100
        )
        
        logger.warning("性能警告", 
            metric_type="response_time",
            value="300ms",
            threshold="200ms",
            recommendation="consider_optimization"
        )
        
        return {
            "metrics_collected": True,
            "records_processed": 100,
            "processing_time": "0.3s",
            "warnings": 1
        }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("启动多应用 OpenTelemetry 演示服务", 
        host="0.0.0.0",
        port=8000,
        otel_endpoint=OTEL_COLLECTOR_ENDPOINT,
        service_info={
            "name": "multi-app-demo",
            "version": "1.0.0",
            "environment": "development"
        }
    )
    
    uvicorn.run(app, host="0.0.0.0", port=8000)