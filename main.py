import asyncio
from core import JobQueue, Worker, JobStatus, RetryStrategy
from handlers.email2 import unreliable_email_handler
from config.settings import RedisConfig
from utils.logger import setup_logger
from demo.demo import demo


if __name__ == "__main__":
    asyncio.run(demo())