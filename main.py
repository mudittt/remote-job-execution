import sys
import click
import asyncio
from pathlib import Path
from cli.commands import cli
from rich.console import Console
from core.queue2 import JobQueue
from utils.logger import setup_logger
from demo.email_demo import EmailDemo
from demo.simple_demo import SimpleDemo
from config.settings import get_redis_config


project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


console = Console()
logger = setup_logger(__name__)

@cli.command()
@click.option('--type', type=click.Choice(['email', 'simple']), default='email', help='Demo type to run')
@click.option('--duration', default=30, help='Duration to run the demo in seconds')
@click.option('--jobs', default=5, help='Number of jobs for simple demo')
def demo(type: str, duration: int, jobs: int):
    async def run():
        with console.status("[cyan]Connecting to Redis queue..."):
            redis_config = get_redis_config()
            queue = JobQueue(redis_config.url)
            await queue.connect()
        console.print("[green]Connected to Redis queue")

        try:
            if type == 'email':
                demo = EmailDemo(queue)
                await demo.run_demo(duration)
            else:
                demo = SimpleDemo(queue)
                await demo.run_demo(jobs, duration)
        finally:
            await queue.close()
    
    asyncio.run(run())

if __name__ == '__main__':
    cli()

