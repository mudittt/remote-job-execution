# Remote Job Execution


## Steps

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