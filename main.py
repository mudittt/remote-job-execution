import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from core.queue2 import JobQueue
from core.enums import JobStatus, RetryStrategy
from config.settings import get_redis_config
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Pydantic models for API
class JobData(BaseModel):
    to: str
    subject: str
    body: Optional[str] = ""

class JobOptions(BaseModel):
    timeout: int = 30
    max_attempts: int = 3
    retry_strategy: str = RetryStrategy.EXPONENTIAL.value
    retry_delay: float = 1.0
    max_retry_delay: float = 300.0

class CreateJobRequest(BaseModel):
    queue_name: str = "email"
    data: JobData
    options: Optional[JobOptions] = JobOptions()

class JobResponse(BaseModel):
    job_id: str
    message: str

# Global variables
queue: Optional[JobQueue] = None
websocket_connections: List[WebSocket] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global queue
    
    logger.info("🚀 Starting job queue web server (API + Dashboard only)...")
    
    # Initialize Redis connection
    redis_config = get_redis_config()
    queue = JobQueue(redis_config.url)
    await queue.connect()
    logger.info("✅ Connected to Redis")
    
    # Start WebSocket broadcaster
    asyncio.create_task(websocket_broadcaster())
    logger.info("✅ WebSocket broadcaster started")
    logger.info("📡 Workers should be started separately using worker.py")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down job queue web server...")
    
    if queue:
        await queue.close()
    
    logger.info("✅ Shutdown completed")

app = FastAPI(
    title="Job Queue API",
    description="Web-based job queue management system",
    version="1.0.0",
    lifespan=lifespan
)

# WebSocket broadcaster for real-time updates
async def websocket_broadcaster():
    while True:
        if websocket_connections and queue:
            try:
                # Get current stats
                stats = await queue.get_queue_stats("email")
                
                
                # Broadcast to all connected clients
                message = {
                    "type": "stats_update",
                    "data": {
                        "queue_stats": stats,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                
                # Send to all connected clients
                disconnected = []
                for websocket in websocket_connections:
                    try:
                        await websocket.send_json(message)
                    except:
                        disconnected.append(websocket)
                
                # Remove disconnected clients
                for ws in disconnected:
                    websocket_connections.remove(ws)
                    
            except Exception as e:
                logger.error(f"Error in WebSocket broadcaster: {e}")
        
        await asyncio.sleep(2)  # Update every 2 seconds

"""
async def get_all_worker_stats():
    try:
        if not queue or not queue.redis:
            return {}
            
        # Get all worker stats keys
        keys = await queue.redis.keys("worker_stats:*")
        all_stats = {}
        
        for key in keys:
            worker_id = key.decode('utf-8').split(':')[1]
            stats_data = await queue.redis.get(key)
            if stats_data:
                stats = json.loads(stats_data)
                # Check if worker is still active (updated within last 10 seconds)
                last_update = datetime.fromisoformat(stats.get('last_update', '1970-01-01T00:00:00'))
                if (datetime.utcnow() - last_update).total_seconds() < 10:
                    all_stats[worker_id] = stats
                else:
                    # Remove stale worker stats
                    await queue.redis.delete(key)
        
        return all_stats
    except Exception as e:
        logger.error(f"Error getting worker stats: {e}")
        return {}
"""
# API Routes
@app.post("/api/jobs", response_model=JobResponse)
async def create_job(request: CreateJobRequest):
    """Create a new job and add it to the queue"""
    if not queue:
        raise HTTPException(status_code=500, detail="Queue not initialized")
    
    try:
        job_data = request.data.dict()
        options = request.options.dict() if request.options else {}
        
        job_id = await queue.enqueue(request.queue_name, job_data, options)
        
        logger.info(f"📝 Job {job_id} created via API")
        return JobResponse(job_id=job_id, message="Job created successfully")
        
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job details by ID"""
    if not queue:
        raise HTTPException(status_code=500, detail="Queue not initialized")
    
    job = await queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job

@app.get("/api/jobs")
async def get_all_jobs():
    """Get all jobs"""
    if not queue:
        raise HTTPException(status_code=500, detail="Queue not initialized")
    
    jobs = await queue.get_all_jobs()
    return {"jobs": jobs, "total": len(jobs)}

@app.get("/api/queue/{queue_name}/stats")
async def get_queue_stats(queue_name: str):
    """Get queue statistics"""
    if not queue:
        raise HTTPException(status_code=500, detail="Queue not initialized")
    
    stats = await queue.get_queue_stats(queue_name)
    return stats

"""
@app.get("/api/worker/stats")
async def get_worker_stats():
    return await get_all_worker_stats()
"""

@app.get("/api/dead-letter-jobs")
async def get_dead_letter_jobs(limit: int = 10):
    """Get jobs from dead letter queue"""
    if not queue:
        raise HTTPException(status_code=500, detail="Queue not initialized")
    
    jobs = await queue.get_dead_letter_jobs(limit)
    return {"dead_letter_jobs": jobs, "count": len(jobs)}

@app.post("/api/jobs/{job_id}/requeue")
async def requeue_dead_job(job_id: str):
    """Requeue a job from dead letter queue"""
    if not queue:
        raise HTTPException(status_code=500, detail="Queue not initialized")
    
    success = await queue.requeue_dead_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be requeued")
    
    return {"message": "Job requeued successfully"}

@app.get("/api/system/status")
async def get_system_status():
    """Get overall system status"""
    if not queue:
        raise HTTPException(status_code=500, detail="System not initialized")
    
    queue_stats = await queue.get_queue_stats("email")
    
    return {
        "system_status": "running",
        "queue_stats": queue_stats,
        "connected_websockets": len(websocket_connections),
        "timestamp": datetime.utcnow().isoformat()
    }

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_connections.append(websocket)
    logger.info(f"🔌 WebSocket connected. Total connections: {len(websocket_connections)}")
    
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info(f"🔌 WebSocket disconnected. Total connections: {len(websocket_connections)}")

# Mount static files and serve HTML
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    with open("templates/dashboard.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)