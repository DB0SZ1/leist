/**
 * List Intel — Workflow Suggestion Toast
 * Shows contextual next-step suggestions after user actions.
 */
(function () {
  'use strict';

  let activeToast = null;
  let autoTimer = null;

  /**
   * Show a workflow suggestion toast.
   * @param {string} title - Bold header text
   * @param {string} description - Supporting description
   * @param {string} actionUrl - Where the CTA button navigates
   * @param {string} actionLabel - CTA button text (default: "Let's go →")
   * @param {string|null} requiredPlan - Plan needed for the action (null = any plan)
   */
  function showWorkflowSuggestion(title, description, actionUrl, actionLabel, requiredPlan) {
    // Remove any existing toast
    dismiss();

    actionLabel = actionLabel || "Let's go →";
    const userPlan = (window.__userPlan || 'free').toLowerCase();

    // Plan hierarchy for gating
    const planLevel = { free: 0, starter: 1, pro: 2, trial: 2 };
    const userLevel = planLevel[userPlan] || 0;
    const requiredLevel = requiredPlan ? (planLevel[requiredPlan] || 0) : 0;
    const locked = requiredPlan && userLevel < requiredLevel;

    const toast = document.createElement('div');
    toast.className = 'wf-toast';
    toast.id = 'wf-toast';
    toast.innerHTML = `
      <div class="wf-toast-header">
        <div class="wf-toast-title">💡 ${title}</div>
        <button class="wf-toast-close" id="wf-toast-close">×</button>
      </div>
      <div class="wf-toast-desc">${description}</div>
      ${locked
        ? `<a href="/billing" class="wf-toast-action">🔒 Upgrade to unlock</a>`
        : `<a href="${actionUrl}" class="wf-toast-action">${actionLabel}</a>`
      }
    `;

    document.body.appendChild(toast);
    activeToast = toast;

    // Animate in
    requestAnimationFrame(() => {
      requestAnimationFrame(() => { toast.classList.add('show'); });
    });

    // Close button
    document.getElementById('wf-toast-close').onclick = dismiss;

    // Auto-dismiss after 12s
    autoTimer = setTimeout(dismiss, 12000);
  }

  function dismiss() {
    if (autoTimer) { clearTimeout(autoTimer); autoTimer = null; }
    if (activeToast) {
      activeToast.classList.remove('show');
      const ref = activeToast;
      setTimeout(() => ref.remove(), 400);
      activeToast = null;
    }
  }

  // Expose globally
  window.showWorkflowSuggestion = showWorkflowSuggestion;
  window.dismissWorkflowToast = dismiss;
})();
