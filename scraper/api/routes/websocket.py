"""
WebSocket Routes for Real-time Job Updates

Provides real-time job progress updates via WebSocket connections.
"""

from typing import Dict, Set
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
import structlog

from scraper.api.models import Job
from scraper.api.job_manager import get_job_manager, JobManager
from scraper.api.middleware.auth import validate_api_key
from scraper.core.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["websocket"])
logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and job subscriptions."""
    
    def __init__(self):
        # Active connections: {websocket: {"job_ids": set, "api_key": str}}
        self.active_connections: Dict[WebSocket, Dict] = {}
        # Job subscriptions: {job_id: set of websockets}
        self.job_subscribers: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, api_key: str):
        """Accept WebSocket connection and authenticate."""
        await websocket.accept()
        self.active_connections[websocket] = {
            "job_ids": set(),
            "api_key": api_key
        }
        logger.info("WebSocket connected", api_key=api_key[:8] + "...")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection and clean up subscriptions."""
        if websocket in self.active_connections:
            connection_info = self.active_connections[websocket]
            
            # Remove from job subscriptions
            for job_id in connection_info["job_ids"]:
                if job_id in self.job_subscribers:
                    self.job_subscribers[job_id].discard(websocket)
                    if not self.job_subscribers[job_id]:
                        del self.job_subscribers[job_id]
            
            del self.active_connections[websocket]
            logger.info("WebSocket disconnected", api_key=connection_info["api_key"][:8] + "...")
    
    def subscribe_to_job(self, websocket: WebSocket, job_id: str):
        """Subscribe WebSocket to job updates."""
        if websocket in self.active_connections:
            self.active_connections[websocket]["job_ids"].add(job_id)
            
            if job_id not in self.job_subscribers:
                self.job_subscribers[job_id] = set()
            self.job_subscribers[job_id].add(websocket)
            
            logger.info("Subscribed to job", job_id=job_id)
    
    def unsubscribe_from_job(self, websocket: WebSocket, job_id: str):
        """Unsubscribe WebSocket from job updates."""
        if websocket in self.active_connections:
            self.active_connections[websocket]["job_ids"].discard(job_id)
            
            if job_id in self.job_subscribers:
                self.job_subscribers[job_id].discard(websocket)
                if not self.job_subscribers[job_id]:
                    del self.job_subscribers[job_id]
            
            logger.info("Unsubscribed from job", job_id=job_id)
    
    async def send_to_job_subscribers(self, job_id: str, message: dict):
        """Send message to all subscribers of a job."""
        if job_id in self.job_subscribers:
            disconnected_connections = set()
            
            for websocket in self.job_subscribers[job_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error("Failed to send WebSocket message", error=str(e))
                    disconnected_connections.add(websocket)
            
            # Clean up disconnected connections
            for websocket in disconnected_connections:
                self.disconnect(websocket)
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send message to specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error("Failed to send personal WebSocket message", error=str(e))
            self.disconnect(websocket)


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str = Query(..., description="API key for authentication"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    WebSocket endpoint for real-time job updates.
    
    Authentication is done via query parameter: ws://host/api/v1/ws?api_key=your-key
    
    Supported messages:
    - {"action": "subscribe", "job_id": "job-id"} - Subscribe to job updates
    - {"action": "unsubscribe", "job_id": "job-id"} - Unsubscribe from job updates
    - {"action": "list_jobs"} - Get list of current jobs
    - {"action": "get_job", "job_id": "job-id"} - Get specific job details
    """
    
    # Authenticate API key
    if not validate_api_key(api_key):
        await websocket.close(code=4001, reason="Invalid API key")
        return
    
    await connection_manager.connect(websocket, api_key)
    
    # Set up job update callback
    async def job_update_callback(job: Job):
        """Callback for job progress updates."""
        message = {
            "type": "job_update",
            "job_id": job.id,
            "job": {
                "id": job.id,
                "type": job.type.value,
                "status": job.status.value,
                "progress": job.progress.model_dump() if job.progress else None,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "result_count": job.result_count,
                "error_message": job.error_message
            }
        }
        await connection_manager.send_to_job_subscribers(job.id, message)
    
    try:
        # Send initial connection confirmation
        await connection_manager.send_personal_message(websocket, {
            "type": "connection_established",
            "message": "Connected to Async Scraper WebSocket"
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action")
                
                if action == "subscribe":
                    job_id = message.get("job_id")
                    if not job_id:
                        await connection_manager.send_personal_message(websocket, {
                            "type": "error",
                            "message": "job_id is required for subscribe action"
                        })
                        continue
                    
                    # Check if job exists
                    job = job_manager.get_job(job_id)
                    if not job:
                        await connection_manager.send_personal_message(websocket, {
                            "type": "error",
                            "message": f"Job {job_id} not found"
                        })
                        continue
                    
                    # Subscribe to job updates
                    connection_manager.subscribe_to_job(websocket, job_id)
                    job_manager.add_progress_callback(job_id, job_update_callback)
                    
                    # Send current job status
                    await connection_manager.send_personal_message(websocket, {
                        "type": "subscribed",
                        "job_id": job_id,
                        "current_status": job.status.value
                    })
                
                elif action == "unsubscribe":
                    job_id = message.get("job_id")
                    if not job_id:
                        await connection_manager.send_personal_message(websocket, {
                            "type": "error",
                            "message": "job_id is required for unsubscribe action"
                        })
                        continue
                    
                    connection_manager.unsubscribe_from_job(websocket, job_id)
                    await connection_manager.send_personal_message(websocket, {
                        "type": "unsubscribed", 
                        "job_id": job_id
                    })
                
                elif action == "list_jobs":
                    jobs = job_manager.list_jobs(limit=50)
                    jobs_data = []
                    
                    for job in jobs:
                        jobs_data.append({
                            "id": job.id,
                            "type": job.type.value,
                            "status": job.status.value,
                            "created_at": job.created_at.isoformat(),
                            "progress": job.progress.model_dump() if job.progress else None
                        })
                    
                    await connection_manager.send_personal_message(websocket, {
                        "type": "jobs_list",
                        "jobs": jobs_data
                    })
                
                elif action == "get_job":
                    job_id = message.get("job_id")
                    if not job_id:
                        await connection_manager.send_personal_message(websocket, {
                            "type": "error",
                            "message": "job_id is required for get_job action"
                        })
                        continue
                    
                    job = job_manager.get_job(job_id)
                    if not job:
                        await connection_manager.send_personal_message(websocket, {
                            "type": "error",
                            "message": f"Job {job_id} not found"
                        })
                        continue
                    
                    await connection_manager.send_personal_message(websocket, {
                        "type": "job_details",
                        "job": {
                            "id": job.id,
                            "type": job.type.value,
                            "status": job.status.value,
                            "created_at": job.created_at.isoformat(),
                            "started_at": job.started_at.isoformat() if job.started_at else None,
                            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                            "progress": job.progress.model_dump() if job.progress else None,
                            "config": job.config,
                            "result_count": job.result_count,
                            "error_message": job.error_message
                        }
                    })
                
                else:
                    await connection_manager.send_personal_message(websocket, {
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
                    
            except json.JSONDecodeError:
                await connection_manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error("WebSocket message processing error", error=str(e))
                await connection_manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Error processing message"
                })
    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
    finally:
        connection_manager.disconnect(websocket)