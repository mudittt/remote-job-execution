import time
import uuid
import json
import redis.asyncio as redis
from utils.logger import setup_logger
from datetime import datetime, timedelta
from .enums import JobStatus, RetryStrategy
from typing import Dict, Any, Optional, Callable, List
# Configure logging

logger = setup_logger(__name__)
class JobQueue:

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        
    async def connect(self):
        try:
            await self.redis.ping()
            logger.info("✅ Successfully connected to Redis")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise ConnectionError(f"Redis connection failed: {e}")

    async def enqueue(
        self, 
        queue_name: str, 
        job_data: Dict[str, Any], 
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        if options is None:
            options = {}
            
        job_id = str(uuid.uuid4())
        job = self._create_job_record(job_id, queue_name, job_data, options)
        
        # Store job in Redis hash for detailed tracking
        await self.redis.hset(f"job:{job_id}", mapping=job)
        
        # Add to queue for processing
        await self.redis.lpush(f"queue:{queue_name}", job_id)
        
        # Track in status index
        await self.redis.sadd(f"jobs:{JobStatus.PENDING.value}", job_id)
        
        logger.info(f"✅ Job {job_id} enqueued to '{queue_name}'")
        return job_id

    async def dequeue(
        self, 
        queue_name: str, 
        timeout: int = 5
    ) -> Optional[Dict[str, Any]]:
        try:
            # Blocking pop from queue (FIFO order)
            result = await self.redis.brpop(f"queue:{queue_name}", timeout=timeout)
            
            if not result:
                return None  # Timeout - no jobs available

            _, job_id = result
            return await self._mark_job_as_processing(job_id)
            
        except Exception as error:
            logger.error(f"Error dequeuing job: {error}")
            return None

    async def mark_job_complete(
        self, 
        job_id: str, 
        result: Optional[Dict[str, Any]] = None
    ):

        current_time = datetime.utcnow()
        
        await self.redis.hset(f"job:{job_id}", mapping={
            'status': JobStatus.COMPLETED.value,
            'completed_at': current_time.isoformat(),
            'updated_at': current_time.isoformat(),
            'result': json.dumps(result or {})
        })
        
        # Update status tracking
        await self._update_job_status_index(job_id, JobStatus.PROCESSING, JobStatus.COMPLETED)
        
        logger.info(f"✅ Job {job_id} completed successfully")

    async def mark_job_failed(self, job_id: str, error: Exception) -> bool:

        job_data = await self.redis.hgetall(f"job:{job_id}")
        attempts = int(job_data.get('attempts', 0)) + 1
        max_attempts = int(job_data.get('max_attempts', 3))
        
        # Record failure in retry history
        retry_history = self._update_retry_history(job_data, attempts, error)
        
        if attempts < max_attempts:
            return await self._schedule_job_retry(job_id, job_data, attempts, error, retry_history)
        else:
            await self._move_to_dead_letter_queue(job_id, error, retry_history)
            return False

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:

        job_data = await self.redis.hgetall(f"job:{job_id}")
        if not job_data:
            return None

        return self._format_job_data(job_data)

    async def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:

        pending_count = await self.redis.llen(f"queue:{queue_name}")
        retry_count = await self.redis.zcard(f"retry:{queue_name}")
        dead_letter_count = await self.redis.llen("dead_letter_queue")
        
        # Count jobs by status
        status_counts = {}
        for status in JobStatus:
            count = await self.redis.scard(f"jobs:{status.value}")
            status_counts[status.value] = count
            
        return {
            'queue_name': queue_name,
            'pending_jobs': pending_count,
            'retry_jobs': retry_count,
            'dead_letter_jobs': dead_letter_count,
            'status_counts': status_counts
        }

    async def get_dead_letter_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:

        job_ids = await self.redis.lrange("dead_letter_queue", 0, limit - 1)
        jobs = []
        
        for job_id in job_ids:
            job = await self.get_job(job_id)
            if job:
                jobs.append(job)
                
        return jobs

    async def requeue_dead_job(self, job_id: str) -> bool:

        job_data = await self.redis.hgetall(f"job:{job_id}")
        
        if not job_data or job_data.get('status') != JobStatus.DEAD.value:
            logger.warning(f"Cannot requeue job {job_id}: not in dead letter queue")
            return False
            
        # Reset job for reprocessing
        current_time = datetime.utcnow()
        await self.redis.hset(f"job:{job_id}", mapping={
            'status': JobStatus.PENDING.value,
            'attempts': 0,
            'updated_at': current_time.isoformat(),
            'last_error': '',
            'retry_history': json.dumps([])
        })
        
        # Move back to active queue
        await self.redis.lrem("dead_letter_queue", 0, job_id)
        await self.redis.lpush(f"queue:{job_data['queue_name']}", job_id)
        
        # Update status tracking
        await self._update_job_status_index(job_id, JobStatus.DEAD, JobStatus.PENDING)
        
        logger.info(f"♻️ Job {job_id} requeued from dead letter queue")
        return True

    async def process_retries(self, queue_name: str):
        current_time = time.time()
        
        # Find jobs ready for retry (score <= current time)
        ready_job_ids = await self.redis.zrangebyscore(
            f"retry:{queue_name}", 
            min=0, 
            max=current_time, 
            withscores=False
        )
        
        for job_id in ready_job_ids:
            await self._move_retry_to_active_queue(job_id, queue_name)

    async def handle_job_timeout(self, job_id: str, timeout: int) -> bool:

        job_data = await self.redis.hgetall(f"job:{job_id}")
        
        if not job_data or job_data.get('status') != JobStatus.PROCESSING.value:
            return False
            
        processing_start = datetime.fromisoformat(job_data['processing_started_at'])
        elapsed_time = (datetime.utcnow() - processing_start).total_seconds()
        
        if elapsed_time > timeout:
            timeout_error = Exception(f"Job timed out after {timeout} seconds")
            await self.mark_job_failed(job_id, timeout_error)
            logger.warning(f"⏰ Job {job_id} timed out after {timeout} seconds")
            return True
            
        return False

    async def close(self):
        await self.redis.aclose()
        logger.info("📤 Redis connection closed")

    # Helpers
    def _create_job_record(
        self, 
        job_id: str, 
        queue_name: str, 
        job_data: Dict[str, Any], 
        options: Dict[str, Any]
    ) -> Dict[str, str]:
            current_time = datetime.utcnow()
            
            return {
                'id': job_id,
                'data': json.dumps(job_data),
                'status': JobStatus.PENDING.value,
                'created_at': current_time.isoformat(),
                'updated_at': current_time.isoformat(),
                'attempts': '0',
                'max_attempts': str(options.get('max_attempts', 3)),
                'queue_name': queue_name,
                'timeout': str(options.get('timeout', 30)),
                'retry_strategy': options.get('retry_strategy', RetryStrategy.EXPONENTIAL.value),
                'retry_delay': str(options.get('retry_delay', 1)),
                'max_retry_delay': str(options.get('max_retry_delay', 300)),
                'processing_started_at': '',
                'last_error': '',
                'retry_history': json.dumps([])
            }
    
    async def _mark_job_as_processing(self, job_id: str) -> Optional[Dict[str, Any]]:
        job_data = await self.redis.hgetall(f"job:{job_id}")
        
        if not job_data:
            logger.warning(f"⚠️ Job {job_id} not found in storage")
            return None

        current_time = datetime.utcnow()
        
        # Update job status to processing
        await self.redis.hset(f"job:{job_id}", mapping={
            'status': JobStatus.PROCESSING.value,
            'processing_started_at': current_time.isoformat(),
            'updated_at': current_time.isoformat()
        })
        
        # Update status tracking
        await self._update_job_status_index(job_id, JobStatus.PENDING, JobStatus.PROCESSING)

        return self._format_job_data(job_data, processing_start=current_time)
    
    def _format_job_data(
        self, 
        job_data: Dict[str, str], 
        processing_start: Optional[datetime] = None
    ) -> Dict[str, Any]:
        return {
            'id': job_data['id'],
            'data': json.loads(job_data.get('data', '{}')),
            'status': job_data.get('status', JobStatus.PENDING.value),
            'created_at': job_data['created_at'],
            'updated_at': job_data.get('updated_at'),
            'processing_started_at': (
                processing_start.isoformat() if processing_start 
                else job_data.get('processing_started_at')
            ),
            'completed_at': job_data.get('completed_at'),
            'failed_at': job_data.get('failed_at'),
            'retry_at': job_data.get('retry_at'),
            'moved_to_dlq_at': job_data.get('moved_to_dlq_at'),
            'attempts': int(job_data.get('attempts', 0)),
            'max_attempts': int(job_data.get('max_attempts', 3)),
            'timeout': int(job_data.get('timeout', 30)),
            'retry_strategy': job_data.get('retry_strategy', RetryStrategy.EXPONENTIAL.value),
            'retry_delay': float(job_data.get('retry_delay', 1)),
            'max_retry_delay': float(job_data.get('max_retry_delay', 300)),
            'last_error': job_data.get('last_error', ''),
            'retry_history': json.loads(job_data.get('retry_history', '[]')),
            'result': json.loads(job_data.get('result', '{}')) if job_data.get('result') else None
        }
    
    def _update_retry_history(
        self, 
        job_data: Dict[str, str], 
        attempts: int, 
        error: Exception
    ) -> List[Dict[str, Any]]:
        retry_history = json.loads(job_data.get('retry_history', '[]'))
        retry_history.append({
            'attempt': attempts,
            'error': str(error),
            'failed_at': datetime.utcnow().isoformat()
        })
        return retry_history
    
    async def _schedule_job_retry(
        self, 
        job_id: str, 
        job_data: Dict[str, str], 
        attempts: int, 
        error: Exception, 
        retry_history: List[Dict[str, Any]]
    ) -> bool:
        delay = self._calculate_retry_delay(
            attempts, 
            job_data.get('retry_strategy', RetryStrategy.EXPONENTIAL.value),
            float(job_data.get('retry_delay', 1)),
            float(job_data.get('max_retry_delay', 300))
        )
        
        retry_time = datetime.utcnow() + timedelta(seconds=delay)
        current_time = datetime.utcnow()
        
        # Update job for retry
        await self.redis.hset(f"job:{job_id}", mapping={
            'status': JobStatus.RETRYING.value,
            'attempts': str(attempts),
            'last_error': str(error),
            'failed_at': current_time.isoformat(),
            'updated_at': current_time.isoformat(),
            'retry_at': retry_time.isoformat(),
            'retry_history': json.dumps(retry_history)
        })
        
        # Schedule retry
        await self.redis.zadd(f"retry:{job_data['queue_name']}", {job_id: time.time() + delay})
        
        # Update status tracking
        await self._update_job_status_index(job_id, JobStatus.PROCESSING, JobStatus.RETRYING)
        
        logger.info(f"🔄 Job {job_id} scheduled for retry in {delay:.1f}s (attempt {attempts}/{job_data.get('max_attempts', 3)})")
        return True
    
    def _calculate_retry_delay(
        self, 
        attempt: int, 
        strategy: str, 
        base_delay: float, 
        max_delay: float
    ) -> float:
        if strategy == RetryStrategy.EXPONENTIAL.value:
            delay = base_delay * (2 ** (attempt - 1))
        elif strategy == RetryStrategy.LINEAR.value:
            delay = base_delay * attempt
        else:  # FIXED strategy
            delay = base_delay
            
        # Add jitter to prevent thundering herd problem
        jitter = delay * 0.1 * (0.5 - abs(hash(str(attempt)) % 1000) / 1000)
        delay += jitter
        
        return min(delay, max_delay)
    
    async def _move_to_dead_letter_queue(
        self, 
        job_id: str, 
        error: Exception, 
        retry_history: List[Dict[str, Any]]
    ):
        current_time = datetime.utcnow()
        
        await self.redis.hset(f"job:{job_id}", mapping={
            'status': JobStatus.DEAD.value,
            'last_error': str(error),
            'updated_at': current_time.isoformat(),
            'moved_to_dlq_at': current_time.isoformat(),
            'retry_history': json.dumps(retry_history)
        })
        
        # Update status tracking and add to dead letter queue
        await self._update_job_status_index(job_id, JobStatus.PROCESSING, JobStatus.DEAD)
        await self.redis.lpush("dead_letter_queue", job_id)
        
        logger.error(f"💀 Job {job_id} moved to dead letter queue after max retries")
    
    async def _move_retry_to_active_queue(self, job_id: str, queue_name: str):
        # Remove from retry schedule
        await self.redis.zrem(f"retry:{queue_name}", job_id)
        
        # Add back to active queue
        await self.redis.lpush(f"queue:{queue_name}", job_id)
        
        # Update job status
        await self.redis.hset(f"job:{job_id}", mapping={
            'status': JobStatus.PENDING.value,
            'updated_at': datetime.utcnow().isoformat()
        })
        
        # Update status tracking
        await self._update_job_status_index(job_id, JobStatus.RETRYING, JobStatus.PENDING)
        
        logger.info(f"🔄 Job {job_id} moved from retry schedule back to active queue")
    
    async def _update_job_status_index(
        self, 
        job_id: str, 
        old_status: JobStatus, 
        new_status: JobStatus
    ):
        await self.redis.srem(f"jobs:{old_status.value}", job_id)
        await self.redis.sadd(f"jobs:{new_status.value}", job_id)

    async def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Fetch all jobs from all status sets and return as a list of job dicts.
        """
        job_ids = set()
        # Collect job IDs from all status sets
        for status in JobStatus:
            ids = await self.redis.smembers(f"jobs:{status.value}")
            job_ids.update(ids)
        # Also include jobs in the dead letter queue (if not already included)
        dlq_ids = await self.redis.lrange("dead_letter_queue", 0, -1)
        job_ids.update(dlq_ids)
        jobs = []
        for job_id in job_ids:
            job_data = await self.redis.hgetall(f"job:{job_id}")
            if job_data:
                jobs.append(self._format_job_data(job_data))
        return jobs

    async def save_job(self, job: Dict[str, Any]):
        """
        Save/overwrite a job dict to Redis hash.
        """
        # Convert fields to string for Redis
        job_to_save = job.copy()
        job_to_save['data'] = json.dumps(job_to_save.get('data', {}))
        job_to_save['retry_history'] = json.dumps(job_to_save.get('retry_history', []))
        if 'result' in job_to_save and job_to_save['result'] is not None:
            job_to_save['result'] = json.dumps(job_to_save['result'])
        else:
            job_to_save['result'] = ''
        # Remove non-primitive fields if any
        for k, v in job_to_save.items():
            if isinstance(v, (int, float)):
                job_to_save[k] = str(v)
        await self.redis.hset(f"job:{job['id']}", mapping=job_to_save)

