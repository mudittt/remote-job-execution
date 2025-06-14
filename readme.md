# REMOTE JOB EXECUTION
Redis-backed job queue system with retry mechanisms, timeouts, and dead letter queues. 

## SETUP

1. Make sure you have git, docker, redis installed.
2. Clone.


## STEPS
1. Open a Terminal, and run
```
docker compose build --no-cache
```
2. Start
```
docker compose up -d
```
3. Go to [localhost:8000](http://127.0.0.1:8000/)
4. To see the logs, run
```
docker compose logs
```
5. To stop, run
```
docker compose down
```



## SCREENSHOTS & SCREEN-RECORDINGS
https://github.com/user-attachments/assets/b7bd3b5b-20b3-4bd2-9faf-54bdffb87c78
<!-- https://github.com/user-attachments/assets/e5101e68-e688-4409-93f9-f28b3223f060 -->

## TODO
- Job Cancellation. <span style="color:green"><strong>[DONE]</strong></span>
- Better / Well formatted Logs. <span style="color:green"><strong>[DONE]</strong></span>
- Using S3 for Logs and Process data.
- Multiple Queues for Multiple Tasks.
- Priority Level Queues.
- Multiple Workers. <span style="color:green"><strong>[DONE]</strong></span>
- Test cases.
