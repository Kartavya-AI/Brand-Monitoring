
import os
import json
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

import aiofiles
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

from src.brand_monitoring.crew import BrandMonitoringCrew

# =====================================================
# Load environment variables
# =====================================================
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# =====================================================
# Globals
# =====================================================
crew_instance = None
analysis_tasks: Dict[str, Any] = {}

# =====================================================
# Utility functions
# =====================================================
def generate_task_id() -> str:
    """Generate a unique task ID."""
    return f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"

async def save_task_result(task_id: str, result: dict):
    """Save task result in /tmp for Cloud Run persistence."""
    try:
        path = f"/tmp/{task_id}.json"
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(result))
        logger.info("Saved task result", task_id=task_id)
    except Exception as e:
        logger.error("Failed to save task result", task_id=task_id, error=str(e))

async def load_task_result(task_id: str) -> Optional[dict]:
    """Load persisted task result."""
    try:
        path = f"/tmp/{task_id}.json"
        if os.path.exists(path):
            async with aiofiles.open(path, "r") as f:
                data = await f.read()
                return json.loads(data)
    except Exception as e:
        logger.error("Failed to load cached result", task_id=task_id, error=str(e))
    return None

def clean_json_output(text: str) -> str:
    """Remove ```json or ``` fences from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

# =====================================================
# Lifespan
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting Brand Monitoring API")

    required_env = ["GEMINI_API_KEY", "SERPAPI_API_KEY", "NEWSAPI_API_KEY"]
    missing = [v for v in required_env if not os.getenv(v)]
    if missing:
        logger.error("Missing environment variables", missing=missing)
        raise RuntimeError(f"Missing required environment variables: {missing}")

    global crew_instance
    try:
        crew_instance = BrandMonitoringCrew()
        logger.info("Crew initialized")
    except Exception as e:
        logger.error("Crew init failed", error=str(e), traceback=traceback.format_exc())
        raise

    yield

    logger.info("Shutting down Brand Monitoring API")
    for task_id, task in analysis_tasks.items():
        if isinstance(task, asyncio.Task) and not task.done():
            task.cancel()
            logger.info("Cancelled running task", task_id=task_id)

# =====================================================
# FastAPI setup
# =====================================================
app = FastAPI(
    title="Brand Monitoring API",
    description="AI-powered Brand Monitoring and Sentiment Analysis with CrewAI",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# =====================================================
# Models
# =====================================================
class BrandMonitoringRequest(BaseModel):
    company_to_search: str = Field(..., min_length=1, max_length=100)
    keywords_to_search: str = Field(..., min_length=1, max_length=500)

    @validator('*')
    def strip_fields(cls, v):
        return v.strip()

class BrandMonitoringResponse(BaseModel):
    task_id: str
    status: str
    message: str
    timestamp: str

# =====================================================
# Exception handlers
# =====================================================
@app.exception_handler(Exception)
async def generic_exception(request: Request, exc: Exception):
    logger.error("Unhandled Exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": str(exc)}
    )

# =====================================================
# Analysis execution
# =====================================================
async def run_analysis(task_id: str, inputs: Dict[str, str]) -> Dict[str, Any]:
    start = datetime.utcnow()
    logger.info("Analysis started", task_id=task_id, inputs=inputs)

    try:
        result = crew_instance.crew().kickoff(inputs=inputs)
        raw_output = str(getattr(result, "raw", result))
        cleaned = clean_json_output(raw_output)

        try:
            json_result = json.loads(cleaned)
        except json.JSONDecodeError:
            json_result = {
                "report_markdown": cleaned,
                "chart_data": {"sentiment": {"Positive": 0, "Negative": 0, "Neutral": 0}}
            }

        elapsed = (datetime.utcnow() - start).total_seconds()
        final = {
            "task_id": task_id,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "execution_time_seconds": elapsed,
            "result": json_result
        }

        await save_task_result(task_id, final)
        logger.info("Analysis completed", task_id=task_id)
        return final

    except Exception as e:
        elapsed = (datetime.utcnow() - start).total_seconds()
        failure = {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "execution_time_seconds": elapsed
        }
        await save_task_result(task_id, failure)
        logger.error("Analysis failed", task_id=task_id, error=str(e))
        return failure

# =====================================================
# Routes
# =====================================================
@app.get("/")
async def root():
    return {"message": "Brand Monitoring API", "version": "1.2.0"}

@app.post("/analyze", response_model=BrandMonitoringResponse)
async def analyze(req: BrandMonitoringRequest):
    if not crew_instance:
        raise HTTPException(status_code=503, detail="Crew not initialized")

    task_id = generate_task_id()
    inputs = req.dict()
    logger.info("New analysis request", task_id=task_id, company=req.company_to_search)

    async def background_task():
        result = await run_analysis(task_id, inputs)
        analysis_tasks[task_id] = result

    task = asyncio.create_task(background_task())
    analysis_tasks[task_id] = task

    return BrandMonitoringResponse(
        task_id=task_id,
        status="started",
        message=f"Analysis started for {req.company_to_search}",
        timestamp=datetime.utcnow().isoformat()
    )

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id in analysis_tasks:
        task = analysis_tasks[task_id]
        if isinstance(task, dict):
            return task
        if not task.done():
            return {"task_id": task_id, "status": "running"}
        result = await task
        analysis_tasks[task_id] = result
        await save_task_result(task_id, result)
        return result

    cached = await load_task_result(task_id)
    if cached:
        return cached

    raise HTTPException(status_code=404, detail="Task not found")

@app.get("/tasks")
async def list_tasks():
    summary = []
    for task_id, task in analysis_tasks.items():
        status = "completed" if isinstance(task, dict) else "running"
        summary.append({"task_id": task_id, "status": status})
    return {"tasks": summary, "count": len(summary)}

@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = analysis_tasks[task_id]
    if isinstance(task, asyncio.Task) and not task.done():
        task.cancel()
    analysis_tasks.pop(task_id, None)

    try:
        os.remove(f"/tmp/{task_id}.json")
    except FileNotFoundError:
        pass

    return {"message": f"Task {task_id} cancelled or removed"}

# =====================================================
# Entry point
# =====================================================
if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

