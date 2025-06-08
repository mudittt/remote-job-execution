# REMOTE JOB EXECUTION
Redis-backed job queue system with retry mechanisms, timeouts, and dead letter queues. 

## SETUP

1. Make sure you have git installed 🤡
2. Clone.
```bash
git clone https://github.com/mudittt/remote-job-execution.git
```
3. Install homebrew.
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

4. Check and Verify.
```bash
brew --version
```
5. Install redis. 
```bash
brew update
```
```bash
brew install redis
```
6. (OPTIONAL) Install medis. 
```bash
brew install medis
```
7. Create a new Virtual Environment. <br/> [Assuming that you are using Miniconda or Anaconda].
```bash
conda create -n noscrubs python=3.10
conda activate noscrubs
```

8. Install necessary packages.
```bash
pip install redis
```
```bash
pip install -r requirements.txt
```


## STEPS
1. Open a Terminal, and <br/> Start the Listners/Workers.<br/> Leave this running in a terminal window. 
```
python main.py start
```
2. Add a job to the Queue.
```
python main.py add --data '{"to": "user@example.com", "subject": "Test Email"}' --options '{"timeout": 10, "max_attempts": 3, "retry_strategy": "exponential"}'
```

3. Show all jobs.
```
python main.py show
```

4. Re-queue a job by ID
```
python main.py process --id <id>
```

5. Stop the Listeners/Workers
```
python main.py stop
```


## SCREENSHOTS & SCREEN-RECORDINGS
https://github.com/user-attachments/assets/e5101e68-e688-4409-93f9-f28b3223f060

## TODO
- Job Cancellation.
- Better / Well formatted Logs. 
- Using S3 for Logs and Process data.
- Multiple Queues for Multiple Tasks <br/> 
    > Tax Invoice Notification <br/>Pick-up & Drop-off Notifications <br/>Updates of a Parcel <br/>Promotional / Discount Mails
- Priority Levels (right now, its just a FIFO based Queue)
- Multiple Workers
- Testing

