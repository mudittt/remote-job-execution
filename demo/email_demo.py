import asyncio
from typing import Optional
from rich.panel import Panel
from rich.table import Table
from core.worker2 import Worker
from core.queue2 import JobQueue
from rich.console import Console
from core.enums import RetryStrategy
from handlers.email2 import unreliable_email_handler
from rich.progress import Progress, SpinnerColumn, TextColumn
from utils.display import display_job_status, display_queue_stats, display_system_stats

console = Console()

class EmailDemo:
    def __init__(self, queue: JobQueue):
        self.queue = queue
        self.worker: Optional[Worker] = None
        self.worker_task: Optional[asyncio.Task] = None

    async def setup_worker(self):
        with console.status("[cyan]Starting email worker..."):
            self.worker = Worker(self.queue, 'email', unreliable_email_handler)
            self.worker_task = asyncio.create_task(self.worker.start())
        console.print("[green]Started email worker")

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

    async def run_demo(self, duration: int):
        await self.setup_worker()
        
        console.print(Panel.fit("Email Job Queue Demo", style="bold blue"))
        
        test_jobs = [
            {
                'data': {'to': 'user1@example.com', 'subject': 'Welcome Email'},
                'options': {
                    'timeout': 10, 
                    'max_attempts': 3, 
                    'retry_strategy': RetryStrategy.EXPONENTIAL.value
                },
                'description': 'Welcome Email (Exponential Retry)'
            },
            {
                'data': {'to': 'user2@example.com', 'subject': 'Newsletter'},
                'options': {
                    'timeout': 5, 
                    'max_attempts': 5, 
                    'retry_strategy': RetryStrategy.LINEAR.value, 
                    'retry_delay': 2
                },
                'description': 'Newsletter (Linear Retry)'
            },
            {
                'data': {'to': 'user3@example.com', 'subject': 'Reminder'},
                'options': {
                    'timeout': 15, 
                    'max_attempts': 2, 
                    'retry_strategy': RetryStrategy.FIXED.value, 
                    'retry_delay': 5
                },
                'description': 'Reminder (Fixed Retry)'
            },
            {
                'data': {'to': 'user4@example.com', 'subject': 'Update Notification'},
                'options': {
                    'timeout': 30, 
                    'max_attempts': 4, 
                    'retry_strategy': RetryStrategy.EXPONENTIAL.value, 
                    'max_retry_delay': 60
                },
                'description': 'Update (Exponential with Max Delay)'
            }
        ]

        # Jobs table
        jobs_table = Table(title="Enqueueing Jobs")
        jobs_table.add_column("Job ID", style="cyan")
        jobs_table.add_column("Email", style="green")
        jobs_table.add_column("Strategy", style="yellow")
        jobs_table.add_column("Max Attempts", justify="center")

        job_ids = []
        for job_config in test_jobs:
            job_id = await self.queue.enqueue('email', job_config['data'], job_config['options'])
            job_ids.append(job_id)
            
            jobs_table.add_row(
                job_id,
                job_config['data']['to'],
                job_config['options']['retry_strategy'],
                str(job_config['options']['max_attempts'])
            )
            await asyncio.sleep(1)

        console.print(jobs_table)

        # Progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Processing jobs for {duration} seconds...", total=None)
            await asyncio.sleep(duration)

        # Display results
        for job_id in job_ids:
            await display_job_status(self.queue, job_id)
        
        await display_queue_stats(self.queue, 'email')
        await display_system_stats(self.queue)

        console.print(Panel("Demo Completed Successfully!", style="bold green"))
        await self.cleanup() 