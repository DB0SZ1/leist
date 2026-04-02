window.startPolling = async function(jobId) {
    const pollInterval = 3000; // 3 secs
    
    async function checkStatus() {
        try {
            const res = await fetch(`/api/v1/jobs/${jobId}`, {
                headers: { 'Authorization': `Bearer ${getAccessToken()}` }
            });
            const data = await res.json();
            if(!data.success) return;
            
            const job = data.data;
            const pct = job.total_emails > 0 ? Math.round((job.processed_emails / job.total_emails) * 100) : 0;
            const uiPct = 50 + Math.floor(pct / 2); // scale 50-100% for the processing phase
            
            if(typeof window.updateProgress === 'function') {
                window.updateProgress(uiPct, `Processing: ${job.processed_emails.toLocaleString()} / ${job.total_emails.toLocaleString()}`);
            }
            
            if(job.status === 'complete') {
                if(typeof window.showComplete === 'function') {
                    window.showComplete(job.total_emails, job.fresh_count || 0, job.burned_count || 0, jobId);
                }
                setTimeout(() => {
                    window.location.href = `/jobs/${jobId}`;
                }, 2000);
            } else if (job.status === 'failed') {
                if(typeof window.showError === 'function') {
                    window.showError("Processing failed", job.error_message || "Encountered a server error.");
                }
            } else {
                setTimeout(checkStatus, pollInterval);
            }
        } catch(err) {
            console.error("Polling error", err);
            setTimeout(checkStatus, pollInterval);
        }
    }
    
    checkStatus();
};
