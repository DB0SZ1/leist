/**
 * List Intel — Onboarding Tour Engine
 * Pure JS spotlight tour — no dependencies.
 */
(function () {
  'use strict';

  const STEPS = [
    { selector: '.logo-sm',        title: 'Welcome to List Intel',    description: 'This is your command centre for email list hygiene, prospecting, and outreach.', position: 'bottom' },
    { selector: '.credits-widget', title: 'Your Credits',             description: 'Credits are consumed when you verify emails. Track your balance and upgrade your plan here.', position: 'right' },
    { selector: '[href="/dashboard"]', title: 'Dashboard',            description: 'Your at-a-glance overview — recent jobs, stats, and quick actions.', position: 'right' },
    { selector: '[href="/jobs"]',   title: 'Job History',             description: 'View all your verification jobs, results, and export cleaned lists.', position: 'right' },
    { selector: '[href="/domains"]', title: 'Domain Health',          description: 'Monitor your sending domains\' reputation and deliverability score.', position: 'right' },
    { selector: '[href="/jobs/compare"]', title: 'Diff Engine',       description: 'Compare two lists side-by-side to find new, removed, or changed contacts.', position: 'right' },
    { selector: '[href="/timing"]', title: 'Campaign Timing',         description: 'Discover the optimal day and hour to send based on historical list performance.', position: 'right' },
    { selector: '[href="/sending/outreach"]', title: 'Outreach',      description: 'Connect your email accounts and launch multi-step outreach sequences.', position: 'right' },
    { selector: '[href="/sourcing"]', title: 'Lead Sourcing',         description: 'Build ideal customer profiles and source fresh prospects from enrichment APIs.', position: 'right' },
    { selector: '[href="/api-keys"]', title: 'API Keys',              description: 'Generate API keys to integrate List Intel into your own tooling.', position: 'right' },
    { selector: '[href="/billing"]', title: 'Billing',                description: 'Manage your subscription, view invoices, and upgrade your plan.', position: 'right' },
    { selector: '[href="/settings"]', title: 'Settings',              description: 'Configure notifications, suppression lists, and account preferences.', position: 'right' },
    { selector: '.upload-card, .upload-zone', title: 'Upload a List', description: 'Drag and drop a CSV here to start your first verification job. That\'s it!', position: 'bottom' },
  ];

  let current = 0;
  let overlay, spotlight, tooltip;

  function findEl(selector) {
    // For comma-separated selectors, try each
    const parts = selector.split(',').map(s => s.trim());
    for (const part of parts) {
      const el = document.querySelector(part);
      if (el) return el;
    }
    return null;
  }

  function createDOM() {
    overlay = document.createElement('div');
    overlay.className = 'tour-overlay';
    overlay.style.opacity = '0';
    document.body.appendChild(overlay);

    spotlight = document.createElement('div');
    spotlight.className = 'tour-spotlight';
    document.body.appendChild(spotlight);

    tooltip = document.createElement('div');
    tooltip.className = 'tour-tooltip';
    document.body.appendChild(tooltip);

    requestAnimationFrame(() => { overlay.style.opacity = '1'; });
  }

  function destroyDOM() {
    if (overlay) { overlay.style.opacity = '0'; setTimeout(() => overlay.remove(), 300); }
    if (spotlight) spotlight.remove();
    if (tooltip) tooltip.remove();
  }

  function renderStep() {
    const step = STEPS[current];
    const el = findEl(step.selector);

    // If element doesn't exist (e.g. locked feature), skip
    if (!el) {
      if (current < STEPS.length - 1) { current++; renderStep(); }
      else { finish(); }
      return;
    }

    const rect = el.getBoundingClientRect();
    const pad = 8;

    // Spotlight
    spotlight.style.top    = (rect.top - pad) + 'px';
    spotlight.style.left   = (rect.left - pad) + 'px';
    spotlight.style.width  = (rect.width + pad * 2) + 'px';
    spotlight.style.height = (rect.height + pad * 2) + 'px';

    // Tooltip position
    tooltip.className = 'tour-tooltip pos-' + step.position;
    const gap = 16;
    switch (step.position) {
      case 'bottom':
        tooltip.style.top  = (rect.bottom + gap) + 'px';
        tooltip.style.left = rect.left + 'px';
        break;
      case 'top':
        tooltip.style.left = rect.left + 'px';
        break;
      case 'right':
        tooltip.style.top  = rect.top + 'px';
        tooltip.style.left = (rect.right + gap) + 'px';
        break;
      case 'left':
        tooltip.style.top  = rect.top + 'px';
        tooltip.style.left = (rect.left - 340) + 'px';
        break;
    }

    // Tooltip content
    tooltip.innerHTML = `
      <div class="tour-title">${step.title}</div>
      <div class="tour-desc">${step.description}</div>
      <div class="tour-footer">
        <span class="tour-counter">${current + 1} / ${STEPS.length}</span>
        <div class="tour-btns">
          ${current > 0 ? '<button class="tour-skip" id="tour-back">Back</button>' : ''}
          <button class="tour-skip" id="tour-skip">Skip</button>
          <button class="tour-next" id="tour-next">${current === STEPS.length - 1 ? 'Finish' : 'Next'}</button>
        </div>
      </div>
    `;

    // After tooltip is rendered, fix top position if 'top'
    if (step.position === 'top') {
      requestAnimationFrame(() => {
        tooltip.style.top = (rect.top - tooltip.offsetHeight - gap) + 'px';
      });
    }

    // Wire buttons
    const nextBtn = document.getElementById('tour-next');
    const skipBtn = document.getElementById('tour-skip');
    const backBtn = document.getElementById('tour-back');

    if (nextBtn) nextBtn.onclick = () => {
      if (current < STEPS.length - 1) { current++; renderStep(); }
      else { finish(); }
    };
    if (skipBtn) skipBtn.onclick = () => finish();
    if (backBtn) backBtn.onclick = () => { if (current > 0) { current--; renderStep(); } };
  }

  function finish() {
    destroyDOM();
    // Mark tour complete via API
    fetch('/api/v1/settings/tour-complete', { method: 'POST' }).catch(() => {});
  }

  function start() {
    current = 0;
    createDOM();
    renderStep();
  }

  // Auto-start if data attribute set
  if (document.body.dataset.startTour === 'true') {
    // Delay slightly so layout is settled
    setTimeout(start, 600);
  }

  // Expose for manual trigger (e.g. settings page "Take tour again" button)
  window.startOnboardingTour = start;
})();
