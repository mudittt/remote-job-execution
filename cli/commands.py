import json
import click
import asyncio
from typing import Optional
from rich.panel import Panel
from core.worker2 import Worker
from core.queue2 import JobQueue
from rich.console import Console
from core.enums import RetryStrategy
from utils.logger import setup_logger
from config.settings import get_redis_config
from handlers.email2 import unreliable_email_handler
from utils.display import display_job_status, display_queue_stats, display_system_stats

console = Console()
logger = setup_logger(__name__)

class JobQueueCLI:
    def __init__(self):
        self.queue: Optional[JobQueue] = None
        self.worker: Optional[Worker] = None
        self.worker_task: Optional[asyncio.Task] = None

    async def setup_queue(self):
        with console.status("[cyan]Connecting to Redis queue..."):
            redis_config = get_redis_config()
            self.queue = JobQueue(redis_config.url)
            await self.queue.connect()
        console.print("[green]Connected to Redis queue")

    async def setup_worker(self, queue_name: str, handler):
        if not self.queue:
            await self.setup_queue()
        
        with console.status(f"[cyan]Starting worker for queue: {queue_name}..."):
            self.worker = Worker(self.queue, queue_name, handler)
            self.worker_task = asyncio.create_task(self.worker.start())
        console.print(f"[green]Started worker for queue: [bold]{queue_name}")

    async def cleanup(self):
        if self.worker:
            console.print("[yellow]Shutting down worker...")
            self.worker.stop()
            await asyncio.sleep(2)
            
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
                
        if self.queue:
            await self.queue.close()
            console.print("[green]Shutdown completed")

    async def add_single_job(self, queue_name: str, email: str, subject: str, 
                           max_attempts: int, timeout: int):
        await self.setup_queue()
        
        job_data = {'to': email, 'subject': subject}
        options = {
            'timeout': timeout,
            'max_attempts': max_attempts,
            'retry_strategy': RetryStrategy.EXPONENTIAL.value
        }
        
        with console.status("[cyan]Adding job to queue..."):
            job_id = await self.queue.enqueue(queue_name, job_data, options)
        
        success_panel = Panel(
            f"[green]Job Added Successfully![/green]\n\n"
            f"[cyan]Job ID:[/cyan] {job_id}\n"
            f"[cyan]Queue:[/cyan] {queue_name}\n"
            f"[cyan]Email:[/cyan] {email}\n"
            f"[cyan]Subject:[/cyan] {subject}\n"
            f"[cyan]Max Attempts:[/cyan] {max_attempts}",
            title="Job Created",
            border_style="green"
        )
        console.print(success_panel)
        return job_id

    async def check_job_status(self, job_id: str):
        await self.setup_queue()
        await display_job_status(self.queue, job_id)

    async def show_queue_stats(self, queue_name: str):
        await self.setup_queue()
        await display_queue_stats(self.queue, queue_name)

    async def show_dead_letter_queue(self, limit: int):
        await self.setup_queue()
        await display_system_stats(self.queue, limit)

    async def start_worker_only(self, queue_name: str):
        await self.setup_worker(queue_name, unreliable_email_handler)
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.cleanup()

@click.group()
def cli():
    pass

@cli.command()
def start():
    async def run():
        cli = JobQueueCLI()
        await cli.setup_worker('email', unreliable_email_handler)
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await cli.cleanup()
    
    asyncio.run(run())

# FIXME: Command to stop a job
@cli.command()
def stop():
    pass

@cli.command()
@click.option('--data', required=True, help='Job data as JSON string')
@click.option('--options', required=True, help='Job options as JSON string')
@click.option('--queue', default='email', help='Queue name')
def add(data, options, queue):
    async def run():
        cli = JobQueueCLI()
        await cli.setup_queue()
        job_data = json.loads(data)
        job_options = json.loads(options)
        job_id = await cli.queue.enqueue(queue, job_data, job_options)
        console.print(f"[green]Job added with ID: {job_id}")
        await cli.cleanup()
    
    asyncio.run(run())

@cli.command()
def show():
    async def run():
        cli = JobQueueCLI()
        await cli.show_queue_stats('email')
        await cli.cleanup()
    
    asyncio.run(run())

@cli.command()
@click.option('--id', 'job_id', required=True, help='Job ID to process')
def process(job_id):
    async def run():
        cli = JobQueueCLI()
        await cli.check_job_status(job_id)
        await cli.cleanup()
    
    asyncio.run(run())

if __name__ == '__main__':
    cli() 