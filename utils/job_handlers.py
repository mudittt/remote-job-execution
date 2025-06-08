from typing import Dict, Any
import asyncio
import random

async def simple_job_handler(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """A simple job handler for testing purposes"""
    task = job_data.get('task', 'unknown')
    value = job_data.get('value', 0)
    
    # Some work
    await asyncio.sleep(random.uniform(0.5, 2.0))
    
    # Occasional failures
    if random.random() < 0.2:
        raise Exception(f"Simulated failure in task {task}")
    
    return {
        'output': f"Processed {task} with value {value}",
        'timestamp': asyncio.get_event_loop().time()
    } 