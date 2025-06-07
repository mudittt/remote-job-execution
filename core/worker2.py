import asyncio
from utils.logger import setup_logger
from .queue2 import JobQueue
from typing import Dict, Any, Optional, Callable, List


logger = setup_logger(__name__)
class Worker:

    def __init__(
        self, 
        queue: JobQueue, 
        queue_name: str, 
        job_handler: Callable[[Dict[str, Any]], Any]
    ):
        self.queue = queue
        self.queue_name = queue_name
        self.job_handler = job_handler
        
        # Worker state
        self.is_running = False
        self._stop_event = asyncio.Event()
        self._current_job = None
        
        # Statistics
        self.processed_jobs = 0
        self.failed_jobs = 0
        self.timed_out_jobs = 0

    async def start(self):
        self.is_running = True
        self._stop_event.clear()
        logger.info(f"🚀 Worker started for queue: {self.queue_name}")
        
        # Start background retry processor
        retry_task = asyncio.create_task(self._retry_processor())
        
        try:
            await self._main_processing_loop()
        finally:
            # Cleanup
            retry_task.cancel()
            try:
                await retry_task
            except asyncio.CancelledError:
                pass
            
            self.is_running = False
            logger.info(
                f"⏹️ Worker stopped. "
                f"Processed: {self.processed_jobs}, "
                f"Failed: {self.failed_jobs}, "
                f"Timed out: {self.timed_out_jobs}"
            )

    async def _main_processing_loop(self):
        while self.is_running and not self._stop_event.is_set():
            try:
                # Get next job from queue
                job = await self.queue.dequeue(self.queue_name, timeout=5)
                
                if job:
                    self._current_job = job
                    logger.info(
                        f"🔄 Processing job {job['id']} "
                        f"(attempt {job['attempts'] + 1}/{job['max_attempts']})"
                    )
                    await self._process_job_with_timeout(job)
                    self._current_job = None
                    
            except asyncio.CancelledError:
                logger.info("Worker processing cancelled")
                break
            except Exception as error:
                logger.error(f"Worker error: {error}")
                await asyncio.sleep(1)  # Brief pause on error

    async def _process_job_with_timeout(self, job: Dict[str, Any]):
        try:
            # Execute job handler with timeout
            result = await asyncio.wait_for(
                self.job_handler(job['data']), 
                timeout=job['timeout']
            )
            
            # Mark as completed
            await self.queue.mark_job_complete(job['id'], result)
            self.processed_jobs += 1
            
        except asyncio.TimeoutError:
            # Handle timeout
            timeout_error = Exception(f"Job timed out after {job['timeout']} seconds")
            await self.queue.mark_job_failed(job['id'], timeout_error)
            self.timed_out_jobs += 1
            logger.warning(f"⏰ Job {job['id']} timed out")
            
        except Exception as error:
            # Handle general errors
            logger.error(f"Error processing job {job['id']}: {error}")
            await self.queue.mark_job_failed(job['id'], error)
            self.failed_jobs += 1

    async def _retry_processor(self):
        while self.is_running:
            try:
                await self.queue.process_retries(self.queue_name)
                await asyncio.sleep(5)  # Check every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error(f"Retry processor error: {error}")
                await asyncio.sleep(5)

    def stop(self):
        logger.info("🛑 Stopping worker...")
        self.is_running = False
        self._stop_event.set()

    def get_stats(self) -> Dict[str, Any]:
        return {
            'queue_name': self.queue_name,
            'is_running': self.is_running,
            'processed_jobs': self.processed_jobs,
            'failed_jobs': self.failed_jobs,
            'timed_out_jobs': self.timed_out_jobs,
            'current_job_id': self._current_job['id'] if self._current_job else None
        }

