const rootWin = (() => {
  try {
    if (window.parent && window.parent.document) return window.parent;
  } catch (_err) {}
  return window;
})();
const rootDoc = rootWin.document;
const OVERFLOW_TOOLTIP_DELAY_MS = 50;
let overflowTooltipEl = null;
let overflowTooltipTimer = null;
let overflowTooltipTarget = null;

function styleButton(button, styles) {
  if (!button) return;
  if (styles.bg) button.style.background = styles.bg;
  if (styles.border) button.style.borderColor = styles.border;
  if (styles.textColor) button.style.color = styles.textColor;
  button.style.transition = 'background-color 120ms ease, border-color 120ms ease, color 120ms ease';

  if (!button.dataset.uiOriginalBg) {
    button.dataset.uiOriginalBg = button.style.background || '';
    button.dataset.uiOriginalBorder = button.style.borderColor || '';
    button.dataset.uiOriginalColor = button.style.color || '';
  }

  if (styles.hoverBg && !button.dataset.uiHoverBound) {
    button.dataset.uiHoverBound = '1';
    button.addEventListener('mouseenter', () => {
      button.style.background = styles.hoverBg;
      button.style.borderColor = styles.hoverBorder || styles.hoverBg;
      button.style.color = styles.hoverTextColor || '#f8fafc';
    });
    button.addEventListener('mouseleave', () => {
      button.style.background = Object.prototype.hasOwnProperty.call(styles, 'bg') ? styles.bg : '';
      button.style.borderColor = Object.prototype.hasOwnProperty.call(styles, 'border') ? styles.border : '';
      button.style.color = Object.prototype.hasOwnProperty.call(styles, 'textColor') ? styles.textColor : '';
    });
  }
}

function applyButtonStyles() {
  const buttons = Array.from(rootDoc.querySelectorAll('button'));
  buttons.forEach((button) => {
    const label = (button.innerText || button.textContent || '').trim();
    if (label === 'Start Now') {
      styleButton(button, { hoverBg: '#2f7d57', hoverBorder: '#256347', hoverTextColor: '#f8fafc' });
    }
    if (label === 'End Now') {
      styleButton(button, { hoverBg: '#b4534d', hoverBorder: '#8f413b', hoverTextColor: '#f8fafc' });
    }
  });
}

function isTextVisiblyTruncated(el) {
  if (!el) return false;
  const style = rootWin.getComputedStyle(el);
  const hasHorizontalTruncation = (el.scrollWidth - el.clientWidth) > 1;
  const lineClamp = Number.parseInt(style.webkitLineClamp || '', 10);
  const hasVerticalTruncation = Number.isFinite(lineClamp) && lineClamp > 0 && (el.scrollHeight - el.clientHeight) > 1;
  const isHidden = style.display === 'none' || style.visibility === 'hidden';
  if (isHidden) return false;
  return hasHorizontalTruncation || hasVerticalTruncation;
}

function ensureOverflowTooltipElement() {
  if (overflowTooltipEl && rootDoc.body.contains(overflowTooltipEl)) return overflowTooltipEl;
  overflowTooltipEl = rootDoc.getElementById('ui-overflow-tooltip-float');
  if (!overflowTooltipEl) {
    overflowTooltipEl = rootDoc.createElement('div');
    overflowTooltipEl.id = 'ui-overflow-tooltip-float';
    rootDoc.body.appendChild(overflowTooltipEl);
  }
  return overflowTooltipEl;
}

function clearOverflowTooltipTimer() {
  if (overflowTooltipTimer) {
    rootWin.clearTimeout(overflowTooltipTimer);
    overflowTooltipTimer = null;
  }
}

function hideOverflowTooltip() {
  clearOverflowTooltipTimer();
  const tooltip = ensureOverflowTooltipElement();
  tooltip.removeAttribute('data-visible');
  overflowTooltipTarget = null;
}

function positionOverflowTooltip(target) {
  if (!target) return;
  const tooltip = ensureOverflowTooltipElement();
  const margin = 8;
  const gap = 6;
  const rect = target.getBoundingClientRect();
  const tipRect = tooltip.getBoundingClientRect();

  let left = rect.left;
  if (left + tipRect.width + margin > rootWin.innerWidth) {
    left = rootWin.innerWidth - tipRect.width - margin;
  }
  left = Math.max(margin, left);

  let top = rect.bottom + gap;
  if (top + tipRect.height + margin > rootWin.innerHeight) {
    top = rect.top - tipRect.height - gap;
  }
  top = Math.max(margin, top);

  tooltip.style.left = `${Math.round(left)}px`;
  tooltip.style.top = `${Math.round(top)}px`;
}

function scheduleOverflowTooltip(target) {
  if (!target) return;
  const text = target.getAttribute('data-ui-overflow-tooltip');
  if (!text) return;
  clearOverflowTooltipTimer();
  overflowTooltipTimer = rootWin.setTimeout(() => {
    const tooltip = ensureOverflowTooltipElement();
    tooltip.textContent = text;
    tooltip.setAttribute('data-visible', '1');
    overflowTooltipTarget = target;
    positionOverflowTooltip(target);
    overflowTooltipTimer = null;
  }, OVERFLOW_TOOLTIP_DELAY_MS);
}

function bindOverflowTooltipHover() {
  if (rootDoc.body.dataset.uiOverflowTooltipHoverBound === '1') return;
  rootDoc.body.dataset.uiOverflowTooltipHoverBound = '1';

  rootDoc.addEventListener('mouseover', (event) => {
    const candidate = event.target instanceof Element
      ? event.target.closest('[data-ui-overflow-tooltip]')
      : null;
    if (!candidate) return;
    if (overflowTooltipTarget === candidate) {
      positionOverflowTooltip(candidate);
      return;
    }
    hideOverflowTooltip();
    scheduleOverflowTooltip(candidate);
  }, true);

  rootDoc.addEventListener('mouseout', (event) => {
    const source = event.target instanceof Element
      ? event.target.closest('[data-ui-overflow-tooltip]')
      : null;
    if (!source) return;
    const related = event.relatedTarget;
    if (related instanceof Element && source.contains(related)) return;
    clearOverflowTooltipTimer();
    if (overflowTooltipTarget === source) hideOverflowTooltip();
  }, true);

  rootDoc.addEventListener('scroll', () => {
    if (overflowTooltipTarget) positionOverflowTooltip(overflowTooltipTarget);
  }, true);
  rootDoc.addEventListener('mousedown', hideOverflowTooltip, true);
  rootDoc.addEventListener('keydown', hideOverflowTooltip, true);
}

function applyOverflowTooltips() {
  const selector = [
    '[data-testid="stMetricLabel"] p',
    '[data-testid="stMetricValue"]',
    '[data-testid="stCaptionContainer"] p',
    '[data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p',
    '[data-testid="stTabs"] button p',
    '.stMarkdown p',
    '.stMarkdown span'
  ].join(', ');

  rootDoc.querySelectorAll(selector).forEach((el) => {
    const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
    if (!text) {
      el.removeAttribute('data-ui-overflow-tooltip');
      if (overflowTooltipTarget === el) hideOverflowTooltip();
      return;
    }
    if (isTextVisiblyTruncated(el)) {
      el.setAttribute('data-ui-overflow-tooltip', text);
    } else {
      el.removeAttribute('data-ui-overflow-tooltip');
      if (overflowTooltipTarget === el) hideOverflowTooltip();
    }
  });
}

function run() {
  applyButtonStyles();
  applyOverflowTooltips();
  bindOverflowTooltipHover();
}

run();
if (!rootDoc.body.dataset.uiOverflowTooltipResizeBound) {
  rootDoc.body.dataset.uiOverflowTooltipResizeBound = '1';
  rootWin.addEventListener('resize', () => {
    rootWin.requestAnimationFrame(run);
    if (overflowTooltipTarget) positionOverflowTooltip(overflowTooltipTarget);
  });
}
const observer = new MutationObserver(run);
observer.observe(rootDoc.body, { childList: true, subtree: true });
