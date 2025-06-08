import asyncio
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.queue2 import JobQueue
from core.worker2 import Worker
from utils.job_handlers import simple_job_handler
from utils.display import display_job_status

console = Console()

class SimpleDemo:
    def __init__(self, queue: JobQueue):
        self.queue = queue
        self.worker: Optional[Worker] = None
        self.worker_task: Optional[asyncio.Task] = None

    async def setup_worker(self):
        """Setup the test worker"""
        with console.status("[cyan]Starting test worker..."):
            self.worker = Worker(self.queue, 'test', simple_job_handler)
            self.worker_task = asyncio.create_task(self.worker.start())
        console.print("[green]Started test worker")

    async def cleanup(self):
        """Cleanup worker resources"""
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

    async def run_demo(self, job_count: int, duration: int):
        await self.setup_worker()
        
        console.print(Panel.fit(f"Simple Demo - {job_count} Jobs", style="bold magenta"))
        
        job_ids = []
        with Progress(console=console) as progress:
            task = progress.add_task("[green]Creating jobs...", total=job_count)
            
            for i in range(job_count):
                job_id = await self.queue.enqueue('test', {'task': f'task_{i}', 'value': i * 10})
                job_ids.append(job_id)
                console.print(f"Enqueued [cyan]{job_id[:8]}...[/cyan] with task_{i}")
                progress.update(task, advance=1)
                await asyncio.sleep(0.5)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[yellow]Processing for {duration} seconds...", total=None)
            await asyncio.sleep(duration)

        # Results table
        results_table = Table(title="Job Results")
        results_table.add_column("Job ID", style="cyan")
        results_table.add_column("Status", style="green")
        results_table.add_column("Result", style="yellow")

        for job_id in job_ids:
            job = await self.queue.get_job(job_id)
            if job:
                status_style = "green" if job['status'] == 'completed' else "red"
                results_table.add_row(
                    job_id,
                    f"[{status_style}]{job['status']}[/{status_style}]",
                    str(job.get('result', {}).get('output', 'N/A'))
                )

        console.print(results_table)
        await self.cleanup() 