window.__li_token = null;

function setToken(token) {
    window.__li_token = token;
}

function getToken() {
    return window.__li_token;
}

function getAccessToken() {
    return window.__li_token;
}

// DevTools Deterrence removed by request

document.addEventListener('alpine:init', () => {
    Alpine.data('toastStore', () => ({
        toasts: [],
        init() {
            window.$toast = this;
        },
        show(type, title, message = '', duration = 4000) {
            const id = Date.now();
            const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
            
            this.toasts.push({ 
                id, type, title, message, 
                icon: icons[type] || '', 
                visible: true,
            });

            if (type !== 'error') {
                setTimeout(() => this.dismiss(id), duration);
            } else {
                setTimeout(() => this.dismiss(id), 8000);
            }
        },
        dismiss(id) {
            const t = this.toasts.find(x => x.id === id);
            if (t) {
                t.visible = false;
                setTimeout(() => {
                    this.toasts = this.toasts.filter(x => x.id !== id);
                }, 200);
            }
        }
    }));

    Alpine.store('modal', {
        openModal: false,
        title: '',
        message: '',
        confirmLabel: 'Confirm',
        danger: false,
        requiresTyping: false,
        typedText: '',
        expectedText: '',
        onConfirm: null,

        open(options) {
            this.title = options.title || 'Confirm';
            this.message = options.message || 'Are you sure?';
            this.confirmLabel = options.confirmLabel || 'Confirm';
            this.danger = options.danger || false;
            this.requiresTyping = options.requiresTyping || false;
            this.expectedText = options.expectedText || '';
            this.typedText = '';
            this.onConfirm = options.onConfirm;
            this.openModal = true;
        },
        close() {
            this.openModal = false;
            this.onConfirm = null;
        },
        confirm() {
            if (this.requiresTyping && this.typedText !== this.expectedText) {
                return;
            }
            if (this.onConfirm) this.onConfirm();
            this.close();
        }
    });
});

async function checkAuthGuard() {
    const publicPaths = ['/', '/login', '/signup', '/verify-email', '/forgot-password', '/reset-password'];
    const isPublic = publicPaths.includes(window.location.pathname) || window.location.pathname.startsWith('/auth/');
    if (!isPublic && !getToken()) {
        try {
            const res = await fetch('/api/v1/auth/refresh', { method: 'POST' });
            if (!res.ok) throw new Error('Refresh failed');
            const data = await res.json();
            if (data.success && data.data && data.data.access_token) {
                setToken(data.data.access_token);
            } else {
                throw new Error('No token');
            }
        } catch (err) {
            window.location.href = '/login';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checkAuthGuard();
});

// Endpoint Obfuscation
const _E = {
    r: (p) => atob(p)
};

async function apiFetch(encodedPath, options = {}) {
    // If someone calls it with raw /api, allow it for backwards compatibility during migration, else decode
    const url = encodedPath.startsWith('/api') ? encodedPath : _E.r(encodedPath);
    
    const defaultHeaders = { 'Content-Type': 'application/json' };
    if (getAccessToken()) {
        defaultHeaders['Authorization'] = `Bearer ${getAccessToken()}`;
    }

    let res;
    try {
        res = await fetch(url, {
            ...options,
            headers: { ...defaultHeaders, ...(options.headers || {}) }
        });
    } catch (e) {
        throw new Error('Network error. Please check your connection.');
    }

    if (res.status === 401) {
        try {
            const refreshRes = await fetch('/api/v1/auth/refresh', { method: 'POST' });
            if (!refreshRes.ok) throw new Error('Cannot refresh');
            const refreshData = await refreshRes.json();
            if (refreshData.success && refreshData.data.access_token) {
                setToken(refreshData.data.access_token);
                defaultHeaders['Authorization'] = `Bearer ${getAccessToken()}`;
                res = await fetch(url, {
                    ...options,
                    headers: { ...defaultHeaders, ...(options.headers || {}) }
                });
            } else {
                throw new Error('Token data missing');
            }
        } catch (e) {
            setToken(null);
            window.location.href = '/login';
            return;
        }
    }

    if (res.headers.get('content-type')?.includes('application/json')) {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            let errMsg = data.message || 'Something went wrong';
            if (data.detail) {
                if (Array.isArray(data.detail)) {
                    errMsg = data.detail[0].msg || data.detail.map(d => d.msg).join(', ');
                } else if (typeof data.detail === 'string') {
                    errMsg = data.detail;
                }
            }
            if (window.$toast) {
                window.$toast.show('error', 'Error', errMsg);
            }
            throw new Error(errMsg);
        }
        return data;
    } else {
        if (!res.ok) {
            throw new Error('API_ERROR');
        }
        return res;
    }
}

function formatCredits(n) {
    if (n === null || n === undefined) return '0';
    return n.toLocaleString('en-US');
}

function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(d);
}

function formatPct(n) {
    if (n === null || n === undefined) return '0%';
    return `${(n * 100).toFixed(1)}%`;
}

function truncateFilename(s, maxLen = 24) {
    if (!s) return '';
    if (s.length <= maxLen) return s;
    const parts = s.split('.');
    if (parts.length > 1) {
        const ext = parts.pop();
        const base = parts.join('.');
        return base.substring(0, maxLen - 4 - ext.length) + '...' + ext;
    }
    return s.substring(0, maxLen - 3) + '...';
}

window.sysConfirm = function(title, msg, confirmText, isDanger, onConfirm) {
    const modal = document.getElementById('sys-modal');
    if (!modal) return;
    
    document.getElementById('sys-modal-title').textContent = title;
    document.getElementById('sys-modal-title').style.color = isDanger ? '#b31c1c' : 'var(--text)';
    
    document.getElementById('sys-modal-msg').textContent = msg;
    
    const iconBase = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none">';
    const dangerIcon = iconBase + '<path d="M12 8v4m0 4h.01" stroke="#b31c1c" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="12" r="9" stroke="#b31c1c" stroke-width="2"/></svg>';
    const warningIcon = iconBase + '<path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" stroke="#964800" stroke-width="1.8" stroke-linejoin="round"/></svg>';
    
    const iconContainer = document.getElementById('sys-modal-icon');
    iconContainer.innerHTML = isDanger ? dangerIcon : warningIcon;
    iconContainer.style.background = isDanger ? '#fcd8d8' : '#fde3c0';

    const btn = document.getElementById('sys-modal-confirm');
    btn.textContent = confirmText;
    btn.className = isDanger ? 'btn-p' : 'btn-primary';
    if (isDanger) {
        btn.style.background = '#e24b4a';
        btn.onmouseover = function() { this.style.background = '#b31c1c'; };
        btn.onmouseout = function() { this.style.background = '#e24b4a'; };
    } else {
        btn.style.background = '';
        btn.onmouseover = null;
        btn.onmouseout = null;
    }
    
    btn.onclick = function() {
        modal.style.display = 'none';
        if (onConfirm) onConfirm();
    };
    
    modal.style.display = 'flex';
};

