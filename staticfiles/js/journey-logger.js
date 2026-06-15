/**
 * Mutisya Frontend Journey Logger
 * Spec: logging rules.md
 *
 * Every user journey gets a traceId.
 * Steps are logged locally + sent to backend via X-Trace-Id header propagation.
 * Never logs passwords, tokens, or sensitive PII.
 */

const JourneyLogger = (() => {
  // ── IDs ──────────────────────────────────────────────────────────────────
  const _sessionId = (() => {
    let id = sessionStorage.getItem('mts_session_id');
    if (!id) { id = 'S' + Math.random().toString(36).slice(2, 10).toUpperCase(); sessionStorage.setItem('mts_session_id', id); }
    return id;
  })();

  let _traceId = null;
  let _journey = null;
  let _journeyStart = null;
  const _userId = document.body.dataset.userId || null;

  function _newTraceId() {
    return 'T' + Math.random().toString(36).slice(2, 10).toUpperCase();
  }

  function _ts() {
    return new Date().toISOString();
  }

  // ── Core emit ─────────────────────────────────────────────────────────────
  function _emit(step, metadata = {}) {
    const entry = {
      timestamp: _ts(),
      traceId: _traceId,
      journey: _journey,
      step,
      userId: _userId,
      sessionId: _sessionId,
      metadata,
    };
    // Always log to console in structured form
    console.log('[JOURNEY]', JSON.stringify(entry));
    return entry;
  }

  // ── Public API ────────────────────────────────────────────────────────────

  /** Start a new named journey (resets traceId) */
  function start(journeyName, metadata = {}) {
    _traceId = _newTraceId();
    _journey = journeyName;
    _journeyStart = performance.now();
    _emit('journey_started', metadata);
    return _traceId;
  }

  /** Log a step within the current journey */
  function step(stepName, metadata = {}) {
    if (!_traceId) start('unknown');
    _emit(stepName, metadata);
  }

  /** Mark journey complete */
  function success(metadata = {}) {
    const duration_ms = _journeyStart ? Math.round(performance.now() - _journeyStart) : null;
    _emit('journey_success', { ...metadata, duration_ms });
  }

  /** Mark journey abandoned/failed */
  function fail(reason, metadata = {}) {
    const duration_ms = _journeyStart ? Math.round(performance.now() - _journeyStart) : null;
    _emit('journey_abandoned', { reason, ...metadata, duration_ms });
  }

  /**
   * Wrap fetch() to:
   * - inject X-Trace-Id header
   * - log request_sent + response_NNN steps
   */
  function tracedFetch(url, options = {}) {
    if (!_traceId) start('api_call');

    options.headers = options.headers || {};
    options.headers['X-Trace-Id'] = _traceId;

    const t0 = performance.now();
    _emit('request_sent', { method: options.method || 'GET', path: url });

    return fetch(url, options).then(response => {
      const duration_ms = Math.round(performance.now() - t0);
      _emit(`response_${response.status}`, {
        method: options.method || 'GET',
        path: url,
        status: response.status,
        duration_ms,
      });
      return response;
    }).catch(err => {
      const duration_ms = Math.round(performance.now() - t0);
      _emit('request_failed', { path: url, error: err.message, duration_ms });
      throw err;
    });
  }

  /** Get current traceId (for injecting into forms as hidden field) */
  function getTraceId() { return _traceId; }

  return { start, step, success, fail, tracedFetch, getTraceId };
})();

// ── Auto-instrument key journeys ──────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const path = location.pathname;

  // ── Login form ──
  const loginForm = document.querySelector('form[action*="login"]');
  if (loginForm) {
    JourneyLogger.start('login', { path });
    JourneyLogger.step('login_page_loaded');
    loginForm.addEventListener('submit', () => {
      JourneyLogger.step('submit_button_clicked');
      JourneyLogger.step('login_request_sent', { path });
    });
  }

  // ── Signup form ──
  const signupForm = document.querySelector('form[action*="signup"]');
  if (signupForm) {
    JourneyLogger.start('signup', { path });
    JourneyLogger.step('signup_page_loaded');
    signupForm.addEventListener('submit', () => {
      JourneyLogger.step('submit_button_clicked');
      JourneyLogger.step('signup_request_sent', { path });
    });
  }

  // ── Checkout form ──
  const checkoutForm = document.querySelector('form[action*="checkout"]');
  if (checkoutForm) {
    JourneyLogger.start('checkout', { path });
    JourneyLogger.step('checkout_opened');
    checkoutForm.addEventListener('submit', () => {
      JourneyLogger.step('payment_submitted');
      JourneyLogger.step('payment_request_sent');
    });
  }

  // ── Product detail page ──
  const productId = document.body.dataset.productId;
  if (productId) {
    JourneyLogger.start('purchase_flow', { productId, path });
    JourneyLogger.step('product_opened', { productId });
  }

  // ── Cart page ──
  if (path === '/cart/') {
    JourneyLogger.start('checkout', { path });
    JourneyLogger.step('cart_opened');
  }

  // ── Order confirm page ──
  if (path.includes('/confirm/')) {
    JourneyLogger.step('payment_success');
    JourneyLogger.success({ path });
  }

  // ── Variant selector changes ──
  document.querySelectorAll('.variant-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      JourneyLogger.step('variant_selected', {
        value: btn.textContent.trim(),
      });
    });
  });

  // ── Tab switches on product detail ──
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.textContent.trim().toLowerCase();
      if (tab.includes('spec')) JourneyLogger.step('technical_specs_viewed');
      else if (tab.includes('review')) JourneyLogger.step('reviews_viewed');
    });
  });

  // ── Search form ──
  const searchForm = document.querySelector('.nav-search');
  if (searchForm) {
    searchForm.addEventListener('submit', () => {
      const q = searchForm.querySelector('input').value.trim();
      JourneyLogger.start('search', { query: q });
      JourneyLogger.step('search_submitted', { query: q });
    });
  }
});

// ── Cart add — patch cartControl to log steps ─────────────────────────────
// cartControl() is defined in base.html; we extend it after Alpine initialises
document.addEventListener('alpine:init', () => {
  // Patch window.dispatchEvent to intercept cart-updated events
  const _orig = window.dispatchEvent.bind(window);
  window.dispatchEvent = function(event) {
    if (event.type === 'cart-updated') {
      JourneyLogger.step('cart_updated', { cart_count: event.detail?.count });
    }
    return _orig(event);
  };
});
