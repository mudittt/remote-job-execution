#!/usr/bin/env python3
"""
Standalone Worker Script

Usage:
    python standaloneworker.py worker1
    python standaloneworker.py worker2
    python standaloneworker.py my_custom_worker
"""

import asyncio
import sys
import signal
from config.settings import get_redis_config
import os
from typing import Dict, Any
from utils.logger import setup_logger
from core.queue2 import JobQueue  # Adjust import path as needed
from core.worker2 import Worker  # Import your Worker class

# Setup logger
logger = setup_logger(__name__)

class StandaloneWorker:
    def __init__(self, worker_name: str, queue_name: str = None):
        self.worker_name = worker_name
        self.queue_name = queue_name or worker_name  # Use worker_name as default queue_name
        self.worker = None
        self.queue = None
        self.shutdown_event = asyncio.Event()
        
    async def job_handler(self, job_data: Dict[str, Any]) -> Any:
        """
        Default job handler - customize this based on your needs.
        This is where you define what each job should do.
        """
        logger.info(f"[{self.worker_name}] Processing job with data: {job_data}")
        
        logger.info(f"[{self.worker_name}] Processing job")
        await asyncio.sleep(10)  # Simulate some work
        return {'status': 'completed', 'data': job_data}
    
    async def initialize(self):
        """Initialize the queue and worker"""
        try:
            # Initialize the job queue
            logger.info(f"🔧 Initializing JobQueue for worker: {self.worker_name}")
            redis_config = get_redis_config()
            self.queue = JobQueue(redis_config.url)
            
            # Check if queue needs connection/initialization
            if hasattr(self.queue, 'connect'):
                logger.info(f"🔌 Connecting to queue...")
                await self.queue.connect()
                logger.info(f"✅ Queue connected successfully")
            
            # Test queue availability
            logger.info(f"🧪 Testing queue availability...")
            try:
                # Try to get queue info or ping the queue
                if hasattr(self.queue, 'get_queue_info'):
                    info = await self.queue.get_queue_info(self.queue_name)
                    logger.info(f"📊 Queue info: {info}")
                elif hasattr(self.queue, 'ping'):
                    await self.queue.ping()
                    logger.info(f"🏓 Queue ping successful")
            except Exception as e:
                logger.warning(f"⚠️ Could not test queue (this might be normal): {e}")
            
            # Initialize the worker
            logger.info(f"👷 Creating Worker instance...")
            self.worker = Worker(
                queue=self.queue,
                queue_name=self.queue_name,
                job_handler=self.job_handler
            )
            
            logger.info(f"✅ Initialized standalone worker: {self.worker_name} -> Queue: {self.queue_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize worker {self.worker_name}: {e}")
            logger.error(f"💡 Make sure your JobQueue class is properly implemented and accessible")
            raise
    
    async def run(self):
        """Main run method"""
        try:
            await self.initialize()
            
            # Setup signal handlers for graceful shutdown
            self.setup_signal_handlers()
            
            logger.info(f"🚀 Starting standalone worker: {self.worker_name}")
            
            # Add a small delay to ensure everything is ready
            await asyncio.sleep(0.1)
            
            # Start monitoring task to log worker status
            monitor_task = asyncio.create_task(self._monitor_worker())
            
            # Start the worker
            logger.info(f"🔄 Starting worker main loop...")
            worker_task = asyncio.create_task(self.worker.start())
            
            # Wait for shutdown signal
            logger.info(f"⏳ Worker {self.worker_name} is now running and waiting for jobs...")
            await self.shutdown_event.wait()
            
            # Graceful shutdown
            logger.info(f"🛑 Shutting down worker: {self.worker_name}")
            monitor_task.cancel()
            self.worker.stop()
            
            # Wait for worker to finish current job
            try:
                await asyncio.wait_for(worker_task, timeout=30)
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Worker {self.worker_name} did not shutdown gracefully")
                worker_task.cancel()
            
            # Print final stats
            stats = self.worker.get_stats()
            logger.info(f"📊 Final stats for {self.worker_name}: {stats}")
            
        except Exception as e:
            logger.error(f"❌ Error running worker {self.worker_name}: {e}")
            raise
        finally:
            # Cleanup
            if self.queue:
                try:
                    if hasattr(self.queue, 'close'):
                        await self.queue.close()
                        logger.info(f"🔌 Queue connection closed")
                except Exception as e:
                    logger.warning(f"⚠️ Error closing queue: {e}")
    
    async def _monitor_worker(self):
        """Monitor worker status and log periodically"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(30)  # Log status every 30 seconds
                if self.worker:
                    stats = self.worker.get_stats()
                    logger.info(f"📈 Worker {self.worker_name} status: {stats}")
        except asyncio.CancelledError:
            logger.info(f"🔍 Monitoring stopped for worker: {self.worker_name}")
        except Exception as e:
            logger.error(f"❌ Monitor error: {e}")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler():
            logger.info(f"🔔 Received shutdown signal for worker: {self.worker_name}")
            self.shutdown_event.set()
        
        # Handle CTRL+C and termination signals
        if sys.platform != 'win32':
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGINT, signal.SIGTERM]:
                loop.add_signal_handler(sig, signal_handler)
        else:
            # Windows doesn't support add_signal_handler
            signal.signal(signal.SIGINT, lambda s, f: signal_handler())
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler())

def print_usage():
    """Print usage information"""
    print("Usage: python standaloneworker.py <worker_name> [queue_name]")
    print("Examples:")
    print("  python standaloneworker.py worker1                    # Listens to queue 'worker1'")
    print("  python standaloneworker.py worker1 email             # Worker 'worker1' listens to queue 'email'")
    print("  python standaloneworker.py email_processor email     # Worker 'email_processor' listens to queue 'email'")
    print("  python standaloneworker.py worker2 test              # Worker 'worker2' listens to queue 'test'")

async def main():
    """Main entry point"""
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print_usage()
        sys.exit(1)
    
    worker_name = sys.argv[1]
    queue_name = sys.argv[2] if len(sys.argv) == 3 else None
    
    if not worker_name or worker_name.strip() == "":
        logger.error("❌ Worker name cannot be empty")
        print_usage()
        sys.exit(1)
    
    # Validate worker name (optional)
    if not worker_name.replace('_', '').replace('-', '').isalnum():
        logger.error("❌ Worker name should contain only alphanumeric characters, hyphens, and underscores")
        sys.exit(1)
    
    # Validate queue name if provided
    if queue_name and not queue_name.replace('_', '').replace('-', '').isalnum():
        logger.error("❌ Queue name should contain only alphanumeric characters, hyphens, and underscores")
        sys.exit(1)
    
    try:
        # Create and run the standalone worker
        standalone_worker = StandaloneWorker(worker_name, queue_name)
        await standalone_worker.run()
        
    except KeyboardInterrupt:
        logger.info("🔔 Received keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    
    logger.info(f"👋 Standalone worker {worker_name} finished")

if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔔 Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)