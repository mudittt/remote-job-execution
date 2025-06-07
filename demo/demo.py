import asyncio
from datetime import datetime
from typing import Dict, Any

# Import job queue components
from core.queue2 import JobQueue
from core.worker2 import Worker
from core.enums import RetryStrategy
from handlers.email2 import unreliable_email_handler
from config.settings import get_redis_config
from utils.logger import setup_logger

# Configure logging
logger = setup_logger(__name__)


async def demo():
    redis_config = get_redis_config()
    
    queue = JobQueue(redis_config.url)
    await queue.connect()

    
    worker = Worker(queue, 'email', unreliable_email_handler)
    worker_task = asyncio.create_task(worker.start())

    try:
        logger.info("\n📋 Adding jobs with different retry configurations...\n")
        
        test_jobs = [
            {
                'data': {'to': 'user1@example.com', 'subject': 'Welcome Email'},
                'options': {
                    'timeout': 10, 
                    'max_attempts': 3, 
                    'retry_strategy': RetryStrategy.EXPONENTIAL.value
                }
            },
            {
                'data': {'to': 'user2@example.com', 'subject': 'Newsletter'},
                'options': {
                    'timeout': 5, 
                    'max_attempts': 5, 
                    'retry_strategy': RetryStrategy.LINEAR.value, 
                    'retry_delay': 2
                }
            },
            {
                'data': {'to': 'user3@example.com', 'subject': 'Reminder'},
                'options': {
                    'timeout': 15, 
                    'max_attempts': 2, 
                    'retry_strategy': RetryStrategy.FIXED.value, 
                    'retry_delay': 5
                }
            },
            {
                'data': {'to': 'user4@example.com', 'subject': 'Update Notification'},
                'options': {
                    'timeout': 30, 
                    'max_attempts': 4, 
                    'retry_strategy': RetryStrategy.EXPONENTIAL.value, 
                    'max_retry_delay': 60
                }
            }
        ]

        job_ids = []
        for job_config in test_jobs:
            job_id = await queue.enqueue('email', job_config['data'], job_config['options'])
            job_ids.append(job_id)
            await asyncio.sleep(1)  # Stagger job submission

        
        logger.info("\n⏳ Processing jobs (including retries and timeout handling)...\n")
        await asyncio.sleep(30)

        
        await display_job_status_report(queue, job_ids)
        
        
        await display_system_statistics(queue, worker)
        
        
        await display_dead_letter_queue(queue)

        logger.info("\n" + "="*60)
        logger.info("✅ DEMONSTRATION COMPLETED")
        logger.info("="*60)

    finally:
        # Graceful shutdown
        await shutdown_worker_and_queue(worker, worker_task, queue)


async def display_job_status_report(queue: JobQueue, job_ids: list):
    
    logger.info("\n" + "="*60)
    logger.info("📊 DETAILED JOB STATUS REPORT")
    logger.info("="*60)
    
    for job_id in job_ids:
        job = await queue.get_job(job_id)
        if job:
            logger.info(f"\nJob {job_id[:8]}...")
            logger.info(f"-----Status: {job['status']}")
            logger.info(f"-----Attempts: {job['attempts']}/{job['max_attempts']}")
            logger.info(f"-----Timeout: {job['timeout']}s")
            logger.info(f"-----Retry Strategy: {job['retry_strategy']}")
            
            if job['last_error']:
                logger.info(f"-----Last Error: {job['last_error']}")
            
            if job['retry_history']:
                logger.info(f"-----Retry History: {len(job['retry_history'])} attempts")


async def display_system_statistics(queue: JobQueue, worker: Worker):
    logger.info("\n" + "="*60)
    logger.info("SYSTEM STATISTICS")
    logger.info("="*60)
    
    queue_stats = await queue.get_queue_stats('email')
    worker_stats = worker.get_stats()
    
    logger.info(f"\n\nQueue Statistics:")
    logger.info(f"-----Pending Jobs: {queue_stats['pending_jobs']}")
    logger.info(f"-----Retry Jobs: {queue_stats['retry_jobs']}")
    logger.info(f"-----Dead Letter Jobs: {queue_stats['dead_letter_jobs']}")
    
    logger.info(f"\n\nStatus Distribution:")
    for status, count in queue_stats['status_counts'].items():
        logger.info(f"-----{status.title()}: {count}")
    
    logger.info(f"\n\nWorker Statistics:")
    logger.info(f"-----Running: {worker_stats['is_running']}")
    logger.info(f"-----Processed: {worker_stats['processed_jobs']}")
    logger.info(f"-----Failed: {worker_stats['failed_jobs']}")
    logger.info(f"-----Timed Out: {worker_stats['timed_out_jobs']}")
    
    if worker_stats['current_job_id']:
        logger.info(f"Current Job: {worker_stats['current_job_id'][:8]}...")


async def display_dead_letter_queue(queue: JobQueue):
    dead_jobs = await queue.get_dead_letter_jobs(5)
    if dead_jobs:
        logger.info("\n" + "="*60)
        logger.info("DEAD LETTER QUEUE")
        logger.info("="*60)
        logger.info(f"\nFound {len(dead_jobs)} jobs in dead letter queue:")
        
        for job in dead_jobs:
            logger.info(f"\n\nJob {job['id'][:8]}...")
            logger.info(f"-----Email: {job['data'].get('to', 'unknown')}")
            logger.info(f"-----Final Error: {job['last_error']}")
            logger.info(f"-----Total Attempts: {job['attempts']}")
            logger.info(f"-----Moved to DLQ: {job.get('moved_to_dlq_at', 'unknown')}")


async def shutdown_worker_and_queue(worker: Worker, worker_task, queue: JobQueue):
    logger.info("\n\n Shutting down worker and closing connections...")
    
    worker.stop()
    await asyncio.sleep(3) 
    worker_task.cancel()
    
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
        
    # Close queue connection
    await queue.close()
    logger.info("Shutdown completed")


async def simple_demo():
    logger.info("Starting simple job queue demo...")
    
    
    redis_config = get_redis_config()
    queue = JobQueue(redis_config.url)
    await queue.connect()
    
    
    worker = Worker(queue, 'test', simple_job_handler)
    worker_task = asyncio.create_task(worker.start())
    
    try:
        job_ids = []
        for i in range(3):
            job_id = await queue.enqueue('test', {'task': f'task_{i}', 'value': i * 10})
            job_ids.append(job_id)
            logger.info(f"✅ Enqueued job {job_id[:8]}... with task_{i}")
        
        # Wait for processing
        await asyncio.sleep(10)
        
        for job_id in job_ids:
            job = await queue.get_job(job_id)
            if job:
                logger.info(f"📊 Job {job_id[:8]}... - Status: {job['status']}")
                if job.get('result'):
                    logger.info(f"   Result: {job['result']}")
    
    finally:
        await shutdown_worker_and_queue(worker, worker_task, queue)


async def simple_job_handler(job_data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"Processing: {job_data}")
    
    # Simulate some work
    await asyncio.sleep(2)
    
    return {
        'processed_at': datetime.now().isoformat(),
        'input': job_data,
        'output': job_data.get('value', 0) * 2
    }


def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'simple':
        asyncio.run(simple_demo())
    else:
        asyncio.run(demo())


if __name__ == "__main__":
    main()