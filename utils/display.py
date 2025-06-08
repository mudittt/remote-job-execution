from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from core.queue2 import JobQueue

console = Console()

async def display_job_status(queue: JobQueue, job_id: str):
    with console.status(f"[cyan]Fetching job {job_id[:8]}..."):
        job = await queue.get_job(job_id)
    
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
            title="Job Status",
            border_style=status_color
        )
        console.print(job_panel)
    else:
        console.print(f"[red]Job {job_id} not found")

async def display_queue_stats(queue: JobQueue, queue_name: str):
    stats = await queue.get_queue_stats(queue_name)
    
    stats_table = Table(title=f"Queue Statistics: {queue_name}")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", justify="right", style="green")
    
    for key, value in stats.items():
        stats_table.add_row(key, str(value))
    
    console.print(stats_table)

async def display_system_stats(queue: JobQueue, limit: int = 5):
    dead_jobs = await queue.get_dead_letter_jobs(limit)
    
    if dead_jobs:
        dlq_table = Table(title="Dead Letter Queue")
        dlq_table.add_column("Job ID", style="red")
        dlq_table.add_column("Email", style="cyan")
        dlq_table.add_column("Attempts", justify="center")
        dlq_table.add_column("Final Error", style="yellow")
        
        for job in dead_jobs:
            dlq_table.add_row(
                job['id'],
                job['data'].get('to', 'unknown'),
                str(job['attempts']),
                job.get('last_error', '')[:40] + "..." if job.get('last_error') else ""
            )
        
        console.print(dlq_table)
    else:
        console.print("[green]No jobs in dead letter queue")