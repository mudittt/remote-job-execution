import logging
import sys
from typing import Optional


def setup_logger(
    name: str = __name__,
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    stream=None
) -> logging.Logger:
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    if stream is None:
        stream = sys.stdout
    
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    
    if not logger.handlers:
        
        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel(level)
        
        
        formatter = logging.Formatter(format_string)
        console_handler.setFormatter(formatter)
        
        
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    return setup_logger(name)


def configure_root_logger(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


# Module level logger
logger = get_logger('job_queue')