import asyncio
import datetime
from datetime import datetime
from utils.logger import setup_logger
from typing import Dict, Any, Optional, Callable, List

logger = setup_logger(__name__)

async def unreliable_email_handler(job_data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"Sending email to: {job_data['to']}")
    
    # Variable processing time
    import random
    processing_time = random.uniform(1, 8)
    await asyncio.sleep(processing_time)
    
    # Different failure scenarios
    # failure_chance = random.random()
    # failure_chance = 0.30
    
    # if failure_chance < 0.15:  
    #     await asyncio.sleep(35)  # Will exceed typical timeout
    # elif failure_chance < 0.35:  
    #     raise Exception("Temporary SMTP server error - retry recommended")
    # elif failure_chance < 0.45:  
    #     raise Exception("Invalid email address - permanent failure")
    
    # Success case
    return {
        'message_id': f"msg_{int(datetime.now().timestamp())}",
        'status': 'sent',
        'processing_time': processing_time
    }

