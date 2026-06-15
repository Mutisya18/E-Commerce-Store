/* store.js — public-facing JS for Mutisya store
 * All Alpine components registered via Alpine.data() for CSP compatibility.
 * All event handlers attached via addEventListener (no on* attributes).
 */


// ── Safe cart parse ───────────────────────────────────────────────────────────

function safeParseCart() {
  const raw = localStorage.getItem('cart');
  if (!raw) return { items: [], count: 0 };
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) throw new Error('bad type');
    // Ensure structure
    if (!Array.isArray(parsed.items)) parsed.items = [];
    if (typeof parsed.count !== 'number') parsed.count = 0;
    return parsed;
  } catch (e) {
    console.warn('[cart] corrupt data, clearing:', raw.substring(0, 50));
    localStorage.removeItem('cart');
    return { items: [], count: 0 };
  }
}

// ── Product card click navigation ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.pc-card[data-href]').forEach(card => {
    card.addEventListener('click', function (e) {
      // Don't navigate if clicking inside cart controls or on links
      if (e.target.closest('.pc-cart, .pc-card-link, button, a')) return;
      window.location.href = this.dataset.href;
    });
  });
});

// ── Cart utilities ────────────────────────────────────────────────────────────

function showCartError(msg) {
  msg = msg || "Couldn't update your cart. Please try again.";
  const el = document.createElement('div');
  el.style.cssText = 'background:#ef4444;color:white;padding:14px 20px;border-radius:8px;font-size:14px;box-shadow:0 10px 30px rgba(0,0,0,.3);animation:pc-slide-in .3s ease;';
  el.textContent = msg;
  const container = document.getElementById('cart-toast-container');
  if (container) container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

const _cartChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('cart') : null;
if (_cartChannel) {
  _cartChannel.onmessage = (e) => {
    try { localStorage.setItem('cart', JSON.stringify(e.data)); } catch (_) {}
    window.dispatchEvent(new CustomEvent('cart-updated', { detail: { count: e.data.count } }));
  };
}
function cartBroadcast(cartState) {
  if (_cartChannel) _cartChannel.postMessage(cartState);
}

window.addEventListener('beforeunload', function () {
  (window._cartControls || []).forEach(function (ctrl) {
    if (ctrl._timer !== null) {
      clearTimeout(ctrl._timer);
      ctrl._timer = null;
      ctrl._sync();
    }
  });
});

// ── Alpine: cartBadge ─────────────────────────────────────────────────────────

document.addEventListener('alpine:init', () => {

  Alpine.data('cartBadge', () => ({
    bump: false,
    count: 0,
    init() {
      try {
        const cart = safeParseCart();
        this.count = cart.count || 0;
      } catch (e) { console.error('[cart-badge] init error', e); }
    },
    update(e) {
      this.count = e.detail.count;
      this.bump = true;
      setTimeout(() => { this.bump = false; }, 350);
    },
  }));

  // ── Alpine: cartControl ───────────────────────────────────────────────────

  Alpine.data('cartControl', () => ({
    productId: 0,
    maxStock: 0,
    quantity: 0,
    error: false,
    _timer: null,
    _committed: 0,

    init() {
      // Read product id and stock from data-* attributes (CSP build requirement)
      this.productId = parseInt(this.$el.dataset.productId) || 0;
      this.maxStock = parseInt(this.$el.dataset.maxStock) || 0;
      try {
        const cart = safeParseCart();
        const item = (cart.items || []).find(i => i.product_id === this.productId);
        if (item) { this.quantity = item.quantity; this._committed = item.quantity; }
      } catch (e) { console.error('[cart-card] init error', e); }
    },

    increment() {
      if (this.quantity >= this.maxStock) return;
      this.quantity++;
      this._updateLocal(this.quantity);
      this._debounce();
    },

    decrement() {
      if (this.quantity <= 0) return;
      this.quantity--;
      this._updateLocal(this.quantity);
      this._debounce();
    },

    _debounce() {
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this._sync(), 400);
      window._cartControls = window._cartControls || [];
      if (!window._cartControls.includes(this)) window._cartControls.push(this);
    },

    _sync() {
      const target = this.quantity;
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
      const body = new URLSearchParams({ product_id: this.productId, quantity: target, csrfmiddlewaretoken: csrf });
      fetch('/cart/add/', { method: 'POST', headers: { 'X-CSRFToken': csrf }, body })
        .then(r => r.json())
        .then(data => {
          if (data.ok) {
            this._committed = target;
            this._updateLocal(target, data.item_id);
            try { cartBroadcast(JSON.parse(localStorage.getItem('cart'))); } catch (_) {}
            window.dispatchEvent(new CustomEvent('cart-updated', { detail: { count: data.cart_count } }));
          } else {
            this._rollback();
          }
        })
        .catch(() => this._rollback());
    },

    _rollback() {
      this.quantity = this._committed;
      this.error = true;
      this._updateLocal(this._committed);
      showCartError();
      setTimeout(() => { this.error = false; }, 3000);
    },

    _updateLocal(qty, itemId) {
      try {
        const cart = JSON.parse(localStorage.getItem('cart') || '{"items":[],"count":0}');
        const idx = cart.items.findIndex(i => i.product_id === this.productId);
        if (qty > 0) {
          const entry = { product_id: this.productId, quantity: qty, item_id: itemId !== undefined ? itemId : (idx >= 0 ? cart.items[idx].item_id : null) };
          if (idx >= 0) cart.items[idx] = entry;
          else cart.items.push(entry);
        } else {
          if (idx >= 0) cart.items.splice(idx, 1);
        }
        cart.count = cart.items.reduce((s, i) => s + i.quantity, 0);
        localStorage.setItem('cart', JSON.stringify(cart));
      } catch (e) { console.error('[cart-card] _updateLocal error', e); }
    },
  }));

  // ── Alpine: cartSummary ───────────────────────────────────────────────────

  Alpine.data('cartSummary', () => {
    const el = document.getElementById('cart-summary-root');
    const initialSubtotal = parseFloat(el ? el.dataset.subtotal : 0) || 0;
    const initialDelivery = parseFloat(el ? el.dataset.delivery : 0) || 0;
    return {
      subtotal: initialSubtotal,
      delivery: initialDelivery,
      init() {
        window.addEventListener('cart-line-changed', (e) => {
          this.subtotal += e.detail.delta;
          if (this.subtotal < 0) this.subtotal = 0;
        });
      },
    };
  });

  // ── Alpine: cartItem ──────────────────────────────────────────────────────

  Alpine.data('cartItem', () => ({
    qty: 0,
    lineTotal: 0,
    unitPrice: 0,
    removing: false,
    gone: false,
    itemId: null,
    sessionKey: '',

    init() {
      this.qty = parseInt(this.$el.dataset.qty) || 0;
      this.itemId = this.$el.dataset.itemId ? parseInt(this.$el.dataset.itemId) : null;
      this.sessionKey = this.$el.dataset.sessionKey || '';
      this.lineTotal = parseFloat(this.$el.dataset.lineTotal) || 0;
      this.unitPrice = parseFloat(this.$el.dataset.unitPrice) || 0;
    },

    csrf() { return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''; },

    updateQty(newQty) {
      const prev = this.qty;
      const prevLine = this.lineTotal;
      this.qty = newQty;
      this.lineTotal = newQty * this.unitPrice;
      fetch('/cart/update/' + (this.itemId || 0) + '/', {
        method: 'POST',
        headers: { 'X-CSRFToken': this.csrf(), 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'quantity=' + newQty + '&session_key=' + this.sessionKey,
      }).then(r => r.json()).then(d => {
        if (d.ok) {
          window.dispatchEvent(new CustomEvent('cart-line-changed', { detail: { delta: this.lineTotal - prevLine } }));
          this._updateLocal(newQty);
          window.dispatchEvent(new CustomEvent('cart-updated', { detail: { count: d.cart_count } }));
          if (d.cart_count === 0) { window.location.reload(); return; }
          if (newQty === 0) this.gone = true;
        } else {
          this.qty = prev; this.lineTotal = prevLine; showCartError();
        }
      }).catch(() => { this.qty = prev; this.lineTotal = prevLine; showCartError(); });
    },

    remove() {
      if (this.removing) return;
      this.removing = true;
      fetch('/cart/remove/' + (this.itemId || 0) + '/', {
        method: 'POST',
        headers: { 'X-CSRFToken': this.csrf(), 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'session_key=' + this.sessionKey,
      }).then(r => r.json()).then(d => {
        if (d.ok) {
          window.dispatchEvent(new CustomEvent('cart-line-changed', { detail: { delta: -this.lineTotal } }));
          this._updateLocal(0);
          window.dispatchEvent(new CustomEvent('cart-updated', { detail: { count: d.cart_count } }));
          if (d.cart_count === 0) { window.location.reload(); return; }
          this.gone = true;
        } else { this.removing = false; showCartError(); }
      }).catch(() => { this.removing = false; showCartError(); });
    },

    _updateLocal(qty) {
      try {
        const cart = JSON.parse(localStorage.getItem('cart') || '{"items":[],"count":0}');
        const idx = cart.items.findIndex(i => i.item_id === this.itemId);
        if (qty > 0 && idx >= 0) cart.items[idx].quantity = qty;
        else if (qty <= 0 && idx >= 0) cart.items.splice(idx, 1);
        cart.count = cart.items.reduce((s, i) => s + i.quantity, 0);
        localStorage.setItem('cart', JSON.stringify(cart));
      } catch (e) {}
    },
  }));

  // ── Alpine: paymentSection ────────────────────────────────────────────────

  Alpine.data('paymentSection', () => {
    const el = document.getElementById('payment-section-root');
    const initial = el ? (el.dataset.method || 'mpesa') : 'mpesa';
    return { method: initial };
  });

  // ── Alpine: productDetail ─────────────────────────────────────────────────

  Alpine.data('productDetail', () => ({
    activeImage: 0,
  }));

  // ── Alpine: reviewSection ─────────────────────────────────────────────────

  Alpine.data('reviewSection', () => {
    const el = document.getElementById('review-section-root');
    const avg = el ? parseFloat(el.dataset.avg) || null : null;
    const count = el ? parseInt(el.dataset.count) || 0 : 0;
    const slug = el ? el.dataset.slug : '';
    return {
      avg,
      count,
      newReviews: [],
      rating: 0,
      body: '',
      submitting: false,
      done: false,
      err: '',
      starsArray(r) { return [1, 2, 3, 4, 5].map(i => i <= Math.round(r)); },
      submit() {
        if (!this.rating || !this.body.trim()) { this.err = 'Please select a rating and write a review.'; return; }
        this.err = ''; this.submitting = true;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
        fetch('/products/' + slug + '/review/', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'rating=' + this.rating + '&body=' + encodeURIComponent(this.body),
        }).then(r => r.json()).then(d => {
          if (d.ok) { this.newReviews.unshift(d.review); this.avg = d.avg; this.count = d.count; this.done = true; }
          else { this.err = d.error || 'Something went wrong.'; }
          this.submitting = false;
        }).catch(() => { this.err = 'Something went wrong.'; this.submitting = false; });
      },
    };
  });

  // ── Alpine: newsletter ────────────────────────────────────────────────────

  Alpine.data('newsletter', () => ({
    email: '',
    sent: false,
    error: '',
    submit() {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
      fetch('/newsletter/subscribe/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'email=' + encodeURIComponent(this.email),
      }).then(r => r.json()).then(d => {
        if (d.ok) { this.sent = true; } else { this.error = d.error; }
      });
    },
  }));

  // ── Alpine: dealCountdown ─────────────────────────────────────────────────

  Alpine.data('dealCountdown', () => ({
    days: 0, hours: 0, mins: 0, secs: 0, expired: false,
    _interval: null,
    init() {
      const deadline = this.$el.dataset.deadline || '';
      const end = new Date(deadline).getTime();
      const tick = () => {
        const diff = end - Date.now();
        if (diff <= 0) { this.expired = true; clearInterval(this._interval); return; }
        this.days = Math.floor(diff / 86400000);
        this.hours = Math.floor((diff % 86400000) / 3600000);
        this.mins = Math.floor((diff % 3600000) / 60000);
        this.secs = Math.floor((diff % 60000) / 1000);
      };
      tick();
      this._interval = setInterval(tick, 1000);
    },
  }));

  Alpine.data('bodyRoot', () => ({}));
  Alpine.data('navbar', () => ({ mobileOpen: false }));
  Alpine.data('accountMenu', () => ({ open: false }));
  Alpine.data('messages', () => ({ show: true }));
  Alpine.data('message', () => ({
    visible: true,
    init() { setTimeout(() => { this.visible = false; }, 7000); },
  }));
  Alpine.data('tabs', () => ({ tab: 'description' }));
  Alpine.data('faqItem', () => ({ open: false }));

}); // end alpine:init

// ── Cart init (runs before Alpine) ───────────────────────────────────────────

(function () {
  const body = document.body;
  const isAuth = body.dataset.userId !== '';
  const cartData = body.dataset.cartState;
  if (isAuth && cartData) {
    try { localStorage.setItem('cart', cartData); } catch (e) {}
  }
})();

// ── Logout modal ──────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const modal = document.getElementById('logout-modal');
  if (!modal) return;

  // Open triggers
  document.querySelectorAll('[data-action="open-logout"]').forEach(el => {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      modal.style.display = 'flex';
    });
  });

  // Close triggers
  document.querySelectorAll('[data-action="close-logout"]').forEach(el => {
    el.addEventListener('click', function () {
      modal.style.display = 'none';
    });
  });

  // Close on overlay click
  modal.addEventListener('click', function (e) {
    if (e.target === modal) modal.style.display = 'none';
  });
});

// ── Filter form auto-submit ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('filter-form');
  if (!form) return;

  form.querySelectorAll('input[type="radio"], input[type="checkbox"], select').forEach(el => {
    el.addEventListener('change', function () { form.submit(); });
  });

  const mobileFilterBtn = document.getElementById('mobile-filter-btn');
  const sidebar = document.querySelector('.filter-sidebar');
  if (mobileFilterBtn && sidebar) {
    mobileFilterBtn.addEventListener('click', function () {
      sidebar.style.display = 'block';
    });
  }
});

// ── Profile modals ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  function openModal(id) { const el = document.getElementById(id); if (el) el.classList.add('open'); }
  function closeModal(id) { const el = document.getElementById(id); if (el) el.classList.remove('open'); }

  document.querySelectorAll('[data-modal-open]').forEach(el => {
    el.addEventListener('click', function () { openModal(this.dataset.modalOpen); });
  });
  document.querySelectorAll('[data-modal-close]').forEach(el => {
    el.addEventListener('click', function () { closeModal(this.dataset.modalClose); });
  });
  document.querySelectorAll('.mp-modal-overlay').forEach(el => {
    el.addEventListener('click', function (e) { if (e.target === el) el.classList.remove('open'); });
  });
});

// ── Username availability check ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  ['username-input', 'profile-username-input'].forEach(function (inputId) {
    const input = document.getElementById(inputId);
    const feedbackId = inputId === 'username-input' ? 'username-feedback' : 'profile-username-feedback';
    const feedback = document.getElementById(feedbackId);
    if (!input || !feedback) return;

    let timeout = null;
    input.addEventListener('input', function () {
      clearTimeout(timeout);
      const username = this.value.trim();
      if (!username) { feedback.textContent = ''; feedback.style.color = ''; return; }
      feedback.textContent = 'Checking...';
      feedback.style.color = '#9A9A9A';
      timeout = setTimeout(() => {
        fetch('/accounts/check-username/?username=' + encodeURIComponent(username))
          .then(r => r.json())
          .then(data => {
            if (data.available === true) { feedback.textContent = data.message; feedback.style.color = '#1A5C45'; }
            else if (data.available === false) { feedback.textContent = data.message; feedback.style.color = '#C0392B'; }
            else { feedback.textContent = ''; }
          })
          .catch(() => { feedback.textContent = ''; });
      }, 2000);
    });
  });
});

// ── Checkout: prevent double-submit + cart clear ──────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('checkout-form');
  if (!form) return;
  form.addEventListener('submit', function () {
    const btn = document.getElementById('place-order-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Placing Order…'; }
    try { localStorage.setItem('cart', '{"items":[],"count":0}'); } catch (e) {}
  });
});

// ── Confirmation page: guest cart clear ───────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const body = document.body;
  if (body.dataset.guestClearCart === '1') {
    try { localStorage.setItem('cart', '{"items":[],"count":0}'); } catch (e) {}
    window.dispatchEvent(new CustomEvent('cart-updated', { detail: { count: 0 } }));
  }
});

// ── Order detail: placeholder actions ────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const trackBtn = document.getElementById('btn-track-order');
  const invoiceBtn = document.getElementById('btn-download-invoice');
  const cancelBtn = document.getElementById('btn-cancel-order');

  if (trackBtn) trackBtn.addEventListener('click', () => alert('Tracking feature coming soon!'));
  if (invoiceBtn) invoiceBtn.addEventListener('click', () => alert('Invoice download coming soon!'));
  if (cancelBtn) {
    const orderNumber = cancelBtn.dataset.orderNumber;
    cancelBtn.addEventListener('click', function () {
      if (confirm('Request cancellation for ' + orderNumber + '?')) {
        alert('Cancellation request submitted!');
      }
    });
  }
});
