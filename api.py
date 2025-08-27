import os
import json
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

from src.brand_monitoring.crew import BrandMonitoringCrew

# Load environment variables
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

# Global variables for crew management
crew_instance = None
analysis_tasks = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Brand Monitoring API")
    
    # Validate required environment variables
    required_env_vars = ["GEMINI_API_KEY", "SERPAPI_API_KEY", "NEWSAPI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error("Missing required environment variables", missing_vars=missing_vars)
        raise RuntimeError(f"Missing required environment variables: {missing_vars}")
    
    # Initialize crew instance
    global crew_instance
    try:
        crew_instance = BrandMonitoringCrew()
        logger.info("Brand monitoring crew initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize crew", error=str(e), traceback=traceback.format_exc())
        raise RuntimeError(f"Failed to initialize crew: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Brand Monitoring API")
    # Clean up any running tasks
    for task_id, task in analysis_tasks.items():
        if not task.done():
            task.cancel()
            logger.info("Cancelled running task", task_id=task_id)

# Create FastAPI app with lifespan
app = FastAPI(
    title="Brand Monitoring API",
    description="AI-powered brand monitoring and sentiment analysis using CrewAI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure this based on your deployment
)

# Pydantic models
class BrandMonitoringRequest(BaseModel):
    """Request model for brand monitoring analysis."""
    company_to_search: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Name of the company/brand to monitor"
    )
    keywords_to_search: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="Comma-separated keywords related to the brand"
    )
    
    @validator('company_to_search')
    def validate_company_name(cls, v):
        if not v.strip():
            raise ValueError('Company name cannot be empty')
        return v.strip()
    
    @validator('keywords_to_search')
    def validate_keywords(cls, v):
        if not v.strip():
            raise ValueError('Keywords cannot be empty')
        return v.strip()

class BrandMonitoringResponse(BaseModel):
    """Response model for brand monitoring analysis."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    timestamp: str = Field(..., description="Request timestamp")

class AnalysisResult(BaseModel):
    """Model for analysis results."""
    task_id: str
    status: str
    result: Optional[Dict[Any, Any]] = None
    error: Optional[str] = None
    timestamp: str
    execution_time_seconds: Optional[float] = None

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error("HTTP exception occurred", 
                status_code=exc.status_code, 
                detail=exc.detail,
                path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unexpected error occurred", 
                error=str(exc),
                traceback=traceback.format_exc(),
                path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Utility functions
def generate_task_id() -> str:
    """Generate a unique task ID."""
    return f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"

async def run_brand_monitoring_analysis(task_id: str, inputs: Dict[str, str]) -> Dict[str, Any]:
    """Run brand monitoring analysis in the background."""
    start_time = datetime.utcnow()
    logger.info("Starting brand monitoring analysis", task_id=task_id, inputs=inputs)
    
    try:
        # Run the crew analysis
        result = crew_instance.crew().kickoff(inputs=inputs)
        
        # Process the result
        if hasattr(result, 'raw'):
            # Extract the raw result if it's a CrewAI result object
            processed_result = str(result.raw)
        else:
            processed_result = str(result)
        
        # Try to parse as JSON if possible
        try:
            json_result = json.loads(processed_result)
        except (json.JSONDecodeError, TypeError):
            # If not valid JSON, wrap in a structured format
            json_result = {
                "report_markdown": processed_result,
                "chart_data": {
                    "sentiment": {"Positive": 0, "Negative": 0, "Neutral": 0},
                    "themes": []
                }
            }
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("Brand monitoring analysis completed", 
                   task_id=task_id, 
                   execution_time_seconds=execution_time)
        
        return {
            "task_id": task_id,
            "status": "completed",
            "result": json_result,
            "timestamp": datetime.utcnow().isoformat(),
            "execution_time_seconds": execution_time
        }
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        error_msg = str(e)
        
        logger.error("Brand monitoring analysis failed", 
                    task_id=task_id, 
                    error=error_msg,
                    execution_time_seconds=execution_time,
                    traceback=traceback.format_exc())
        
        return {
            "task_id": task_id,
            "status": "failed",
            "error": error_msg,
            "timestamp": datetime.utcnow().isoformat(),
            "execution_time_seconds": execution_time
        }

# API Routes
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Brand Monitoring API",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    try:
        # Check if crew instance is available
        if crew_instance is None:
            raise HTTPException(status_code=503, detail="Crew instance not initialized")
        
        # Check environment variables
        required_vars = ["GEMINI_API_KEY", "SERPAPI_API_KEY", "NEWSAPI_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise HTTPException(status_code=503, detail=f"Missing environment variables: {missing_vars}")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "active_tasks": len([t for t in analysis_tasks.values() if not t.done()])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.post("/analyze", response_model=BrandMonitoringResponse)
async def start_brand_monitoring(
    request: BrandMonitoringRequest, 
    background_tasks: BackgroundTasks
):
    """Start brand monitoring analysis."""
    
    if crew_instance is None:
        logger.error("Crew instance not available")
        raise HTTPException(
            status_code=503, 
            detail="Service not ready. Crew instance not initialized."
        )
    
    # Generate task ID
    task_id = generate_task_id()
    
    # Prepare inputs for crew
    inputs = {
        'company_to_search': request.company_to_search,
        'keywords_to_search': request.keywords_to_search
    }
    
    logger.info("Starting new brand monitoring task", 
               task_id=task_id, 
               company=request.company_to_search)
    
    # Create and start background task
    async def background_analysis():
        result = await run_brand_monitoring_analysis(task_id, inputs)
        analysis_tasks[task_id] = result
    
    # Create asyncio task
    task = asyncio.create_task(background_analysis())
    analysis_tasks[task_id] = task
    
    return BrandMonitoringResponse(
        task_id=task_id,
        status="started",
        message=f"Brand monitoring analysis started for {request.company_to_search}",
        timestamp=datetime.utcnow().isoformat()
    )

@app.get("/status/{task_id}")
async def get_analysis_status(task_id: str):
    """Get the status of a brand monitoring analysis."""
    
    if task_id not in analysis_tasks:
        raise HTTPException(
            status_code=404, 
            detail=f"Task {task_id} not found"
        )
    
    task = analysis_tasks[task_id]
    
    # If task is a dictionary (completed result), return it
    if isinstance(task, dict):
        return task
    
    # If task is still running
    if not task.done():
        return {
            "task_id": task_id,
            "status": "running",
            "message": "Analysis in progress",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Task is done, get the result
    try:
        result = await task
        # Store the result for future queries
        analysis_tasks[task_id] = result
        return result
    except Exception as e:
        logger.error("Error retrieving task result", task_id=task_id, error=str(e))
        error_result = {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
        analysis_tasks[task_id] = error_result
        return error_result

@app.get("/tasks")
async def list_tasks():
    """List all analysis tasks and their statuses."""
    
    task_summaries = []
    
    for task_id, task in analysis_tasks.items():
        if isinstance(task, dict):
            # Completed task
            task_summaries.append({
                "task_id": task_id,
                "status": task.get("status", "unknown"),
                "timestamp": task.get("timestamp", "unknown")
            })
        else:
            # Running task
            status = "completed" if task.done() else "running"
            task_summaries.append({
                "task_id": task_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    return {
        "tasks": task_summaries,
        "total_tasks": len(task_summaries),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running analysis task."""
    
    if task_id not in analysis_tasks:
        raise HTTPException(
            status_code=404, 
            detail=f"Task {task_id} not found"
        )
    
    task = analysis_tasks[task_id]
    
    # If it's a completed result, just remove it
    if isinstance(task, dict):
        del analysis_tasks[task_id]
        return {
            "message": f"Task {task_id} result cleared",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # If it's a running task, cancel it
    if not task.done():
        task.cancel()
        logger.info("Task cancelled", task_id=task_id)
    
    del analysis_tasks[task_id]
    
    return {
        "message": f"Task {task_id} cancelled and removed",
        "timestamp": datetime.utcnow().isoformat()
    }

# For local development
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )