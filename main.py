import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import job queue components
from core.queue2 import JobQueue
from core.worker2 import Worker
from core.enums import RetryStrategy
from handlers.email2 import unreliable_email_handler
from config.settings import get_redis_config
from utils.logger import setup_logger

# Configure rich console
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

    async def run_full_demo(self, duration: int):
        
        await self.setup_worker('email', unreliable_email_handler)
        
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

        # Create jobs table
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

        # Processing with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Processing jobs for {duration} seconds...", total=None)
            await asyncio.sleep(duration)

        await self.display_job_status_report(job_ids)
        await self.display_system_statistics()
        await self.display_dead_letter_queue()

        console.print(Panel("Demo Completed Successfully!", style="bold green"))

    async def run_simple_demo(self, job_count: int, duration: int):
        await self.setup_worker('test', self.simple_job_handler)
        
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
        
        # Success panel
        success_panel = Panel(
            f"[green]✅ Job Added Successfully![/green]\n\n"
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
        
        with console.status(f"[cyan]Fetching job {job_id[:8]}..."):
            job = await self.queue.get_job(job_id)
        
        if job:
            status_color = {
                'pending': 'yellow',
                'processing': 'blue', 
                'completed': 'green',
                'failed': 'red',
                'retrying': 'orange'
            }.get(job['status'], 'white')
            
            job_panel = Panel(
                f"[cyan]Job ID:[/cyan] {job_id}\n"
                f"[cyan]Status:[/cyan] [{status_color}]{job['status']}[/{status_color}]\n"
                f"[cyan]Attempts:[/cyan] {job['attempts']}/{job['max_attempts']}\n"
                f"[cyan]Created:[/cyan] {job.get('created_at', 'unknown')}\n"
                f"[cyan]Timeout:[/cyan] {job['timeout']}s\n"
                f"[cyan]Strategy:[/cyan] {job['retry_strategy']}\n" +
                (f"[cyan]Last Error:[/cyan] [red]{job['last_error']}[/red]\n" if job.get('last_error') else "") +
                (f"[cyan]Result:[/cyan] [green]{job['result']}[/green]" if job.get('result') else ""),
                title=f"Job Status: {job_id[:8]}...",
                border_style=status_color
            )
            console.print(job_panel)
        else:
            console.print(f"[red]Job {job_id} not found")

    async def show_queue_stats(self, queue_name: str):
        await self.setup_queue()
        
        with console.status(f"[cyan]Fetching stats for queue '{queue_name}'..."):
            stats = await self.queue.get_queue_stats(queue_name)
        
        # Stats table
        stats_table = Table(title=f"Queue Statistics: {queue_name}")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Count", justify="right", style="green")
        
        stats_table.add_row("Pending Jobs", str(stats['pending_jobs']))
        stats_table.add_row("Retry Jobs", str(stats['retry_jobs']))
        stats_table.add_row("Dead Letter Jobs", str(stats['dead_letter_jobs']))
        
        console.print(stats_table)
        
        # Status distribution table
        if stats['status_counts']:
            status_table = Table(title="Status Distribution")
            status_table.add_column("Status", style="cyan")
            status_table.add_column("Count", justify="right", style="yellow")
            
            for status, count in stats['status_counts'].items():
                status_table.add_row(status.title(), str(count))
            
            console.print(status_table)

    async def show_dead_letter_queue(self, limit: int):
        await self.setup_queue()
        await self.display_dead_letter_queue(limit)

    async def start_worker_only(self, queue_name: str):
        handler = unreliable_email_handler if queue_name == 'email' else self.simple_job_handler
        await self.setup_worker(queue_name, handler)
        
        console.print(f"[green]Worker started for queue '[bold]{queue_name}[/bold]'")
        console.print("[yellow]Press Ctrl+C to stop...[/yellow]")
        
        try:
            while True:
                await asyncio.sleep(5)
                stats = self.worker.get_stats()
                
                # Live stats display
                live_panel = Panel(
                    f"[green]Processed:[/green] {stats['processed_jobs']}\n"
                    f"[red]Failed:[/red] {stats['failed_jobs']}\n"  
                    f"[blue]Running:[/blue] {stats['is_running']}\n"
                    f"[yellow]Timed Out:[/yellow] {stats['timed_out_jobs']}",
                    title="Live Worker Stats",
                    border_style="blue"
                )
                console.print(live_panel)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]🛑 Stopping worker...[/yellow]")

    # Helper methods
    async def display_job_status_report(self, job_ids: list):
        console.print("\n")
        status_table = Table(title="📊 Detailed Job Status Report")
        status_table.add_column("Job ID", style="cyan")
        status_table.add_column("Status", style="green")
        status_table.add_column("Attempts", justify="center")
        status_table.add_column("Strategy", style="yellow")
        status_table.add_column("Error", style="red")
        
        for job_id in job_ids:
            job = await self.queue.get_job(job_id)
            if job:
                status_color = {
                    'completed': 'green',
                    'failed': 'red', 
                    'pending': 'yellow',
                    'retrying': 'orange'
                }.get(job['status'], 'white')
                
                status_table.add_row(
                    job_id[:8] + "...",
                    f"[{status_color}]{job['status']}[/{status_color}]",
                    f"{job['attempts']}/{job['max_attempts']}",
                    job['retry_strategy'],
                    job.get('last_error', '')[:30] + "..." if job.get('last_error') else ""
                )
        
        console.print(status_table)

    async def display_system_statistics(self):
        console.print("\n")
        
        queue_stats = await self.queue.get_queue_stats('email')
        worker_stats = self.worker.get_stats()
        
        # System stats panel
        system_panel = Panel(
            f"[cyan]Queue Stats:[/cyan]\n"
            f"  Pending: {queue_stats['pending_jobs']}\n"
            f"  Retry: {queue_stats['retry_jobs']}\n"
            f"  Dead Letter: {queue_stats['dead_letter_jobs']}\n\n"
            f"[cyan]Worker Stats:[/cyan]\n"
            f"  Processed: {worker_stats['processed_jobs']}\n"
            f"  Failed: {worker_stats['failed_jobs']}\n"
            f"  Timed Out: {worker_stats['timed_out_jobs']}",
            title="System Statistics",
            border_style="blue"
        )
        console.print(system_panel)

    async def display_dead_letter_queue(self, limit: int = 5):
        dead_jobs = await self.queue.get_dead_letter_jobs(limit)
        
        if dead_jobs:
            dlq_table = Table(title="💀 Dead Letter Queue")
            dlq_table.add_column("Job ID", style="red")
            dlq_table.add_column("Email", style="cyan")
            dlq_table.add_column("Attempts", justify="center")
            dlq_table.add_column("Final Error", style="yellow")
            
            for job in dead_jobs:
                dlq_table.add_row(
                    job['id'][:8] + "...",
                    job['data'].get('to', 'unknown'),
                    str(job['attempts']),
                    job.get('last_error', '')[:40] + "..." if job.get('last_error') else ""
                )
            
            console.print(dlq_table)
        else:
            console.print("[green]No jobs in dead letter queue")

    async def simple_job_handler(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(2)  # Simulate work
        return {
            'processed_at': datetime.now().isoformat(),
            'input': job_data,
            'output': job_data.get('value', 0) * 2
        }

    # Legacy demo method (for backward compatibility)
    async def run_legacy_demo(self):
        console.print(Panel.fit("Running Legacy Demo", style="bold yellow"))
        await self.run_full_demo(30)


# CLI setup with Click
@click.group()
def cli():
    pass

@cli.command()
def start():
    """Start the worker service."""
    async def run():
        cli_instance = JobQueueCLI()
        try:
            await cli_instance.setup_worker('email', unreliable_email_handler)
            console.print("[green]Worker started. Press Ctrl+C to stop.[/green]")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("[yellow]Stopping worker...[/yellow]")
        finally:
            await cli_instance.cleanup()
    asyncio.run(run())

@cli.command()
def stop():
    console.print("[yellow]To stop the worker, use Ctrl+C in the terminal running START.[/yellow]")

@cli.command()
@click.option('--data', required=True, help='Job data as JSON string')
@click.option('--options', required=True, help='Job options as JSON string')
@click.option('--queue', default='email', help='Queue name')
def add(data, options, queue):
    
    import json
    async def run():
        cli_instance = JobQueueCLI()
        try:
            job_data = json.loads(data)
            job_options = json.loads(options)
            await cli_instance.setup_queue()
            await cli_instance.queue.enqueue(queue, job_data, job_options)
            console.print("[green]Successfully pushed into the queue.[/green]")
        finally:
            await cli_instance.cleanup()
    asyncio.run(run())

@cli.command()
def show():
    async def run():
        cli_instance = JobQueueCLI()
        try:
            await cli_instance.setup_queue()
            jobs = await cli_instance.queue.get_all_jobs()  
            if not jobs:
                console.print("[yellow]No jobs found in the system.")
                return
            table = Table(title="All Jobs")
            table.add_column("Job ID", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Attempts", justify="center")
            table.add_column("Queue", style="magenta")
            table.add_column("Error", style="red")
            for job in jobs:
                status_color = {
                    'pending': 'yellow',
                    'processing': 'blue',
                    'completed': 'green',
                    'failed': 'red',
                    'retrying': 'orange',
                    'cancelled': 'grey'
                }.get(job['status'], 'white')
                queue_val = job.get('queue_name') or job.get('queue') or 'unknown'
                table.add_row(
                    job['id'],
                    f"[{status_color}]{job['status']}[/{status_color}]",
                    f"{job['attempts']}/{job['max_attempts']}",
                    queue_val,
                    job.get('last_error', '')[:30] + "..." if job.get('last_error') else ""
                )
            console.print(table)
        finally:
            await cli_instance.cleanup()
    asyncio.run(run())

@cli.command()
@click.option('--id', 'job_id', required=True, help='Job ID to process')
def process(job_id):
    async def run():
        cli_instance = JobQueueCLI()
        try:
            await cli_instance.setup_queue()
            job = await cli_instance.queue.get_job(job_id)
            if not job:
                console.print(f"[red]Job {job_id} not found.")
                return
            job['attempts'] = 0
            job['status'] = 'pending'
            job['last_error'] = ''
            await cli_instance.queue.save_job(job)  
            await cli_instance.queue.enqueue(job.get('queue', 'email'), job['data'], job['options'], job_id=job_id)
            console.print(f"[green]Job {job_id} re-queued for processing.")
        finally:
            await cli_instance.cleanup()
    asyncio.run(run())

if __name__ == "__main__":
    cli()

