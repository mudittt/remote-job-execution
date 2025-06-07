import os
from enum import Enum
from typing import Optional
from dataclasses import dataclass


class RetryStrategy(Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 30
    socket_connect_timeout: int = 30
    decode_responses: bool = True
    
    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    @classmethod
    def from_env(cls) -> 'RedisConfig':
        return cls(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            db=int(os.getenv('REDIS_DB', '0')),
            password=os.getenv('REDIS_PASSWORD'),
            socket_timeout=int(os.getenv('REDIS_SOCKET_TIMEOUT', '30')),
            socket_connect_timeout=int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '30'))
        )


@dataclass
class JobConfig:
    max_attempts: int = 3
    timeout: int = 30
    retry_strategy: str = RetryStrategy.EXPONENTIAL.value
    retry_delay: float = 1.0
    max_retry_delay: float = 300.0
    
    def to_dict(self) -> dict:
        return {
            'max_attempts': self.max_attempts,
            'timeout': self.timeout,
            'retry_strategy': self.retry_strategy,
            'retry_delay': self.retry_delay,
            'max_retry_delay': self.max_retry_delay
        }
    
    @classmethod
    def from_env(cls) -> 'JobConfig':
        return cls(
            max_attempts=int(os.getenv('JOB_MAX_ATTEMPTS', '3')),
            timeout=int(os.getenv('JOB_TIMEOUT', '30')),
            retry_strategy=os.getenv('JOB_RETRY_STRATEGY', RetryStrategy.EXPONENTIAL.value),
            retry_delay=float(os.getenv('JOB_RETRY_DELAY', '1.0')),
            max_retry_delay=float(os.getenv('JOB_MAX_RETRY_DELAY', '300.0'))
        )


@dataclass
class WorkerConfig:
    queue_name: str = "default"
    polling_timeout: int = 5
    retry_check_interval: int = 5
    graceful_shutdown_timeout: int = 30
    max_concurrent_jobs: int = 1
    
    @classmethod
    def from_env(cls, queue_name: str = "default") -> 'WorkerConfig':
        return cls(
            queue_name=queue_name,
            polling_timeout=int(os.getenv('WORKER_POLLING_TIMEOUT', '5')),
            retry_check_interval=int(os.getenv('WORKER_RETRY_CHECK_INTERVAL', '5')),
            graceful_shutdown_timeout=int(os.getenv('WORKER_GRACEFUL_SHUTDOWN_TIMEOUT', '30')),
            max_concurrent_jobs=int(os.getenv('WORKER_MAX_CONCURRENT_JOBS', '1'))
        )




DEFAULT_REDIS_CONFIG = RedisConfig()
DEFAULT_JOB_CONFIG = JobConfig()
DEFAULT_WORKER_CONFIG = WorkerConfig()


def get_redis_config() -> RedisConfig:
    return RedisConfig.from_env()


def get_job_config() -> JobConfig:
    return JobConfig.from_env()


def get_worker_config(queue_name: str = "default") -> WorkerConfig:
    return WorkerConfig.from_env(queue_name)
