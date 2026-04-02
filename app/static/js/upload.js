let currentJobId = null;
let isMergeMode = false;

function toggleMergeMode() {
    const toggle = document.getElementById('merge-toggle');
    if(!toggle) return;
    isMergeMode = toggle.checked;
    
    const fileInput = document.getElementById('file-input');
    if (isMergeMode) {
        fileInput.multiple = true;
        document.getElementById('uz-drop-title').innerText = "Drop up to 10 CSVs to merge";
    } else {
        fileInput.multiple = false;
        document.getElementById('uz-drop-title').innerText = "Drop your CSV here";
    }
}

function handleDragOver(e) {
    e.preventDefault();
    document.getElementById('uz-default').classList.add('drag');
}

function handleDragLeave(e) {
    e.preventDefault();
    document.getElementById('uz-default').classList.remove('drag');
}

function handleDrop(e) {
    e.preventDefault();
    handleDragLeave(e);
    if(e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        if (isMergeMode) {
            processFiles(e.dataTransfer.files);
        } else {
            processFiles([e.dataTransfer.files[0]]);
        }
    }
}

function handleFileSelect(e) {
    if(e.target.files && e.target.files.length > 0) {
        if (isMergeMode) {
            processFiles(e.target.files);
        } else {
            processFiles([e.target.files[0]]);
        }
    }
}

async function processFiles(fileList) {
    hideAllUploadStates();
    
    let totalSize = 0;
    const formData = new FormData();
    const isMerging = isMergeMode && fileList.length > 1;

    if (isMergeMode && fileList.length < 2) {
        showError("Too few files", "Please select at least 2 files to merge.");
        return;
    }
    if (isMerging && fileList.length > 10) {
        showError("Too many files", "You can only merge up to 10 CSVs at once.");
        return;
    }
    
    for(let i=0; i<fileList.length; i++) {
        let file = fileList[i];
        if(!file.name.endsWith('.csv')) {
            showError("Invalid format", "Only .csv files are supported.");
            return;
        }
        totalSize += file.size;
        formData.append(isMerging ? "files" : "file", file);
    }
    
    if(totalSize > 50 * 1024 * 1024) {
        showError("File too large", "Maximum combined file size is 50MB.");
        return;
    }

    document.getElementById('uz-uploading').style.display = 'block';
    
    if (isMerging) {
        document.getElementById('uz-filename').innerText = `Merging ${fileList.length} files...`;
        document.getElementById('uz-filemeta').innerText = `${(totalSize/1024/1024).toFixed(1)} MB total`;
        // Always enrich the merged result automatically
        formData.append("enrich", "true");
    } else {
        document.getElementById('uz-filename').innerText = fileList[0].name;
        document.getElementById('uz-filemeta').innerText = `${(totalSize/1024/1024).toFixed(1)} MB · Detecting rows...`;
    }
    
    document.getElementById('uz-progress-fill').style.width = '5%';
    document.getElementById('uz-progress-pct').innerText = '5%';
    document.getElementById('uz-progress-text').innerText = 'Uploading...';

    const url = isMerging ? '/api/v1/jobs/merge' : '/api/v1/jobs';

    try {
        const res = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: { 'Authorization': `Bearer ${getAccessToken()}` }
        });
        
        const data = await res.json();
        if(!data.success) {
            const msg = data.message || "Something went wrong.";
            if(msg.toLowerCase().includes("credit")) {
                showNoCredits(msg);
            } else {
                showError("Upload failed", msg);
            }
            return;
        }

        if (isMerging) {
            document.getElementById('uz-filemeta').innerText = `Deduplicating and processing ${data.data.total_emails} records...`;
        } else {
            document.getElementById('uz-filemeta').innerText = `Detected email column: '${data.data.email_column || 'Email'}'`;
        }
        currentJobId = data.data.id;
        
        document.getElementById('uz-progress-fill').style.width = '50%';
        document.getElementById('uz-progress-pct').innerText = '50%';
        document.getElementById('uz-progress-text').innerText = 'Processing...';

        if (typeof window.startPolling === 'function') {
            window.startPolling(currentJobId);
        } else {
            console.error('startPolling not defined');
        }
        
    } catch(err) {
        console.error(err);
        showError("Upload failed", "Network error.");
    }
}

function hideAllUploadStates() {
    ['uz-default', 'uz-uploading', 'uz-complete', 'uz-error', 'uz-no-credits'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.style.display = 'none';
    });
}

function showError(title, msg) {
    hideAllUploadStates();
    document.getElementById('uz-error').style.display = 'block';
    document.getElementById('uz-error-title').innerText = title;
    document.getElementById('uz-error-msg').innerText = msg;
}

function showNoCredits(msg) {
    hideAllUploadStates();
    document.getElementById('uz-no-credits').style.display = 'block';
    if(msg) document.getElementById('uz-credits-msg').innerText = msg;
}

function showComplete(total, fresh, burned, jobId) {
    hideAllUploadStates();
    document.getElementById('uz-complete').style.display = 'block';
    document.getElementById('uz-result-meta').innerText = `${total.toLocaleString()} emails · ${fresh.toLocaleString()} fresh · ${burned.toLocaleString()} burned`;
    document.getElementById('uz-view-results').href = `/jobs/${jobId}`;
}

function updateProgress(pct, statusText) {
    const fill = document.getElementById('uz-progress-fill');
    const pctTxt = document.getElementById('uz-progress-pct');
    const txt = document.getElementById('uz-progress-text');
    
    if(fill) fill.style.width = `${pct}%`;
    if(pctTxt) pctTxt.innerText = `${pct}%`;
    if(txt) txt.innerText = statusText || 'Processing...';
}

function resetUploadZone() {
    hideAllUploadStates();
    document.getElementById('uz-default').style.display = 'block';
    document.getElementById('file-input').value = "";
    currentJobId = null;
}
