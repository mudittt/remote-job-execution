let ws = null;
// Initialize WebSocket connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    ws.onopen = function() {
        document.getElementById('connection-status').textContent = 'Connected';
        document.querySelector('.status-indicator').className = 'status-indicator status-running';
    };
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type === 'stats_update') {
            updateStats(data.data);
        }
    };
    ws.onclose = function() {
        document.getElementById('connection-status').textContent = 'Disconnected';
        document.querySelector('.status-indicator').className = 'status-indicator status-failed';
        setTimeout(connectWebSocket, 3000);
    };
    ws.onerror = function() {
        document.getElementById('connection-status').textContent = 'Error';
        document.querySelector('.status-indicator').className = 'status-indicator status-failed';
    };
}
function updateStats(data) {
    const queueStats = data.queue_stats;
    document.getElementById('pending-jobs').textContent = queueStats.pending_jobs || 0;
    document.getElementById('processing-jobs').textContent = queueStats.status_counts?.processing || 0;
    document.getElementById('completed-jobs').textContent = queueStats.status_counts?.completed || 0;
    document.getElementById('failed-jobs').textContent = queueStats.status_counts?.dead || 0;
    document.getElementById('retry-jobs').textContent = queueStats.retry_jobs || 0;
}
function toggleJobForm() {
    const form = document.getElementById('job-form');
    form.classList.toggle('hidden');
    document.getElementById('jobs-table').classList.add('hidden');
}
async function createJob(event) {
    event.preventDefault();
    const jobData = {
        queue_name: 'email',
        data: {
            to: document.getElementById('job-email').value,
            subject: document.getElementById('job-subject').value,
            body: document.getElementById('job-body').value
        },
        options: {
            max_attempts: parseInt(document.getElementById('job-attempts').value),
            timeout: parseInt(document.getElementById('job-timeout').value)
        }
    };
    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });
        if (response.ok) {
            const result = await response.json();
            alert(`Job created successfully! ID: ${result.job_id}`);
            document.getElementById('job-form').classList.add('hidden');
            event.target.reset();
        } else {
            alert('Error creating job');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
async function loadAllJobs() {
    try {
        const response = await fetch('/api/jobs');
        const data = await response.json();
        displayJobs(data.jobs, 'All Jobs');
    } catch (error) {
        alert('Error loading jobs: ' + error.message);
    }
}
async function loadDeadJobs() {
    try {
        const response = await fetch('/api/dead-letter-jobs');
        const data = await response.json();
        displayJobs(data.dead_letter_jobs, 'Dead Letter Queue');
    } catch (error) {
        alert('Error loading dead jobs: ' + error.message);
    }
}
function displayJobs(jobs, title) {
    document.getElementById('jobs-title').textContent = title;
    document.getElementById('job-form').classList.add('hidden');
    document.getElementById('jobs-table').classList.remove('hidden');
    const tbody = document.getElementById('jobs-tbody');
    tbody.innerHTML = '';
    jobs.forEach(job => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${job.id}</td>
            <td><span class="status-indicator status-${job.status === 'completed' ? 'running' : job.status === 'dead' ? 'failed' : 'pending'}"></span>${job.status}</td>
            <td>${job.data?.to || '-'}</td>
            <td>${job.data?.subject || '-'}</td>
            <td>${job.attempts}/${job.max_attempts}</td>
            <td>${new Date(job.created_at).toLocaleString()}</td>
            <td>
                ${job.status === 'dead' ? 
                    `<button class="btn btn-primary" onclick="requeueJob('${job.id}')">Requeue</button>` : 
                    `<button class="btn" onclick="viewJob('${job.id}')">View</button>`
                }
            </td>
        `;
    });
}
async function requeueJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}/requeue`, { method: 'POST' });
        if (response.ok) {
            alert('Job requeued successfully!');
            loadDeadJobs();
        } else {
            alert('Error requeuing job');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
function viewJob(jobId) {
    window.open(`/api/jobs/${jobId}`, '_blank');
}
async function refreshStats() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        updateStats(data);
    } catch (error) {
        console.error('Error refreshing stats:', error);
    }
}
connectWebSocket();
refreshStats();
