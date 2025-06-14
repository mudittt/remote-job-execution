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
1. Open a Terminal, and start the server
```
python run_server.py
```
2. Go to [localhost:8000](http://127.0.0.1:8000/)
3. Add a few Jobs in the queue. 
4. Run the Workers
```
python standaloneworker.py <worker_name> <queue_name>
```
Example:
```
python standaloneworker.py w1 email
```
```
python standaloneworker.py w2 email
```


## SCREENSHOTS & SCREEN-RECORDINGS
https://github.com/user-attachments/assets/e5101e68-e688-4409-93f9-f28b3223f060

## TODO
- Job Cancellation.
- Better / Well formatted Logs. 
- Using S3 for Logs and Process data.
- Multiple Queues for Multiple Tasks <br/> 
    > Tax Invoice Notification <br/>Pick-up & Drop-off Notifications <br/>Updates of a Parcel <br/>Promotional / Discount Mails
- Priority Level Queues
- Multiple Workers <span style="color:green"><strong>[DONE]</strong></span>
- Testing

