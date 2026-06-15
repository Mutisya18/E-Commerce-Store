/* dashboard.js — dashboard-only JS for Mutisya admin
 * All Alpine components registered via Alpine.data() for CSP compatibility.
 * All event handlers attached via addEventListener (no on* attributes).
 */

// ── CSRF helper ───────────────────────────────────────────────────────────────

function getCsrf() {
  const el = document.getElementById('dashboard-root');
  return (el && el.dataset.csrf) || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
}

// ── Alpine: overviewStats (dashboard home) ────────────────────────────────────

document.addEventListener('alpine:init', () => {

  Alpine.data('bodyRoot', () => ({}));

  Alpine.data('overviewStats', (initialPeriod) => {
    let chartInstance = null;
    const root = document.getElementById('overview-stats-root');
    const stats = root ? JSON.parse(root.dataset.stats) : {};

    return {
      period: initialPeriod || 'month',
      stats,
      init() {
        this.$nextTick(() => {
          if (chartInstance) return;
          const ctx = document.getElementById('salesChart');
          if (!ctx || typeof Chart === 'undefined') return;
          let labels, data;
          if (this.period === 'today') {
            labels = ['12am', '4am', '8am', '12pm', '4pm', '8pm', 'Now'];
            data = [0, 2000, 8000, 15000, 22000, 28000, this.stats.period_revenue];
          } else if (this.period === 'week') {
            labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            data = [12000, 19000, 15000, 25000, 22000, 30000, this.stats.period_revenue];
          } else {
            labels = ['Week 1', 'Week 2', 'Week 3', 'Week 4'];
            data = [45000, 62000, 58000, this.stats.period_revenue];
          }
          chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
              labels,
              datasets: [{
                label: 'Revenue',
                data,
                borderColor: '#1B2A4A',
                backgroundColor: 'rgba(27, 42, 74, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2,
                pointRadius: 4,
                pointBackgroundColor: '#1B2A4A',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
              }],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: false } },
              scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { callback: v => 'KES ' + (v / 1000).toFixed(0) + 'k' } },
                x: { grid: { display: false } },
              },
            },
          });
        });
      },
    };
  });

}); // end alpine:init

// ── Orders page ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const listView = document.getElementById('listView');
  if (!listView) return; // not on orders page

  const STORAGE_KEY = 'orders_view';
  const PAGE_SIZE = 15;
  let currentPage = 1;
  let visibleRows = [];

  function setView(v) {
    const kb = document.getElementById('kanbanView');
    const btnL = document.getElementById('btnList');
    const btnK = document.getElementById('btnKanban');
    const tabs = document.getElementById('statusTabs');
    if (v === 'kanban') {
      listView.style.display = 'none';
      kb.style.display = 'block';
      btnK.classList.add('active');
      btnL.classList.remove('active');
      tabs.style.visibility = 'hidden';
      document.querySelectorAll('.k-col').forEach(col => { col.style.display = ''; });
    } else {
      listView.style.display = 'block';
      kb.style.display = 'none';
      btnL.classList.add('active');
      btnK.classList.remove('active');
      tabs.style.visibility = 'visible';
    }
    try { localStorage.setItem(STORAGE_KEY, v); } catch (e) {}
  }

  // Expose for pagination buttons built dynamically
  window.goPage = function (n) { currentPage = n; renderPage(); };

  document.getElementById('btnList').addEventListener('click', () => setView('list'));
  document.getElementById('btnKanban').addEventListener('click', () => setView('kanban'));

  try { if (localStorage.getItem(STORAGE_KEY) === 'kanban') setView('kanban'); } catch (e) {}

  document.querySelectorAll('#statusTabs .status-tab').forEach(btn => {
    btn.addEventListener('click', function () {
      document.querySelectorAll('#statusTabs .status-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPage = 1;
      applyFilter();
    });
  });

  let searchTimer;
  document.getElementById('orderSearch').addEventListener('input', function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { currentPage = 1; applyFilter(); }, 300);
  });

  function applyFilter() {
    const activeTab = document.querySelector('#statusTabs .status-tab.active');
    const status = activeTab ? activeTab.dataset.filter : 'all';
    const q = document.getElementById('orderSearch').value.toLowerCase().trim();
    visibleRows = [];
    document.querySelectorAll('#ordersTbody tr.o-row').forEach(row => {
      const match = (status === 'all' || (row.dataset.status || '').trim() === status) &&
                    (!q || row.dataset.search.includes(q));
      if (match) visibleRows.push(row);
    });
    renderPage();
  }

  function renderPage() {
    const total = visibleRows.length;
    const totalPages = Math.ceil(total / PAGE_SIZE);
    if (currentPage > totalPages) currentPage = Math.max(1, totalPages);
    const start = (currentPage - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    document.querySelectorAll('#ordersTbody tr.o-row').forEach(row => row.classList.add('hidden'));
    visibleRows.forEach((row, i) => row.classList.toggle('hidden', i < start || i >= end));

    const pg = document.getElementById('pagination');
    if (totalPages <= 1) { pg.style.display = 'none'; return; }
    pg.style.display = 'flex';
    let html = currentPage === 1
      ? '<span class="pg-btn nav" aria-disabled="true">← Previous</span>'
      : '<button class="pg-btn nav" data-page="' + (currentPage - 1) + '">← Previous</button>';
    for (let i = 1; i <= totalPages; i++) {
      if (i === currentPage) html += '<span class="pg-btn current">' + i + '</span>';
      else if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2))
        html += '<button class="pg-btn" data-page="' + i + '">' + i + '</button>';
      else if (i === currentPage - 3 || i === currentPage + 3)
        html += '<span class="pg-btn" style="cursor:default">…</span>';
    }
    html += currentPage === totalPages
      ? '<span class="pg-btn nav" aria-disabled="true">Next →</span>'
      : '<button class="pg-btn nav" data-page="' + (currentPage + 1) + '">Next →</button>';
    pg.innerHTML = html;
    pg.querySelectorAll('[data-page]').forEach(btn => {
      btn.addEventListener('click', function () { currentPage = parseInt(this.dataset.page); renderPage(); });
    });
  }

  applyFilter();
});

// ── Products page ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const productsTbody = document.getElementById('productsTbody');
  if (!productsTbody) return;

  const CSRF = getCsrf();

  // Stock edit
  window.startStockEdit = function (pk, current, threshold) {
    const wrap = document.getElementById('stock-wrap-' + pk);
    const visCell = document.getElementById('vis-cell-' + pk);
    wrap.innerHTML = '<input class="stock-input" id="stock-input-' + pk + '" type="number" min="0" value="' + current + '">';
    visCell.innerHTML =
      '<div style="display:flex;gap:8px;align-items:center">' +
      '<button class="stock-confirm-btn" data-action="save" data-pk="' + pk + '" data-threshold="' + threshold + '" title="Save" style="color:var(--emerald)"><svg class="icon" width="14" height="14" fill="currentColor" aria-hidden="true"><use href="#ph-check"></use></svg></button>' +
      '<button class="stock-confirm-btn" data-action="cancel" data-pk="' + pk + '" data-current="' + current + '" data-threshold="' + threshold + '" title="Cancel" style="color:var(--danger)"><svg class="icon" width="14" height="14" fill="currentColor" aria-hidden="true"><use href="#ph-x"></use></svg></button>' +
      '</div>';
    visCell.querySelector('[data-action="save"]').addEventListener('click', function () {
      saveStock(parseInt(this.dataset.pk), parseInt(this.dataset.threshold));
    });
    visCell.querySelector('[data-action="cancel"]').addEventListener('click', function () {
      renderStockVal(parseInt(this.dataset.pk), parseInt(this.dataset.current), parseInt(this.dataset.threshold));
    });
    const input = document.getElementById('stock-input-' + pk);
    input.focus(); input.select();
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') saveStock(pk, threshold);
      if (e.key === 'Escape') renderStockVal(pk, current, threshold);
    });
  };

  function saveStock(pk, threshold) {
    const input = document.getElementById('stock-input-' + pk);
    const val = Math.max(0, parseInt(input.value) || 0);
    fetch('/dashboard/products/' + pk + '/stock/', {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
      body: JSON.stringify({ stock: val }),
    }).then(r => r.json()).then(data => renderStockVal(pk, data.stock, threshold));
  }
  window.saveStock = saveStock;
  window.cancelStockEdit = function (pk, current, threshold) { renderStockVal(pk, current, threshold); };

  function renderStockVal(pk, stock, threshold) {
    const color = stock === 0 ? 'var(--danger)' : stock <= threshold ? 'var(--warning)' : 'var(--emerald)';
    const wrap = document.getElementById('stock-wrap-' + pk);
    wrap.innerHTML =
      '<span class="stock-val" id="stock-val-' + pk + '" style="color:' + color + '">' + stock + '</span>' +
      '<button class="stock-edit-btn" style="opacity:1" data-pk="' + pk + '" data-stock="' + stock + '" data-threshold="' + threshold + '" title="Edit stock"><svg class="icon" width="11" height="11" fill="currentColor" aria-hidden="true"><use href="#ph-pencil-simple"></use></svg></button>';
    wrap.querySelector('.stock-edit-btn').addEventListener('click', function () {
      startStockEdit(parseInt(this.dataset.pk), parseInt(this.dataset.stock), parseInt(this.dataset.threshold));
    });
    const visCell = document.getElementById('vis-cell-' + pk);
    const row = wrap.closest('tr');
    const checked = row.dataset.vis === 'visible';
    visCell.innerHTML =
      '<label class="toggle"><input type="checkbox"' + (checked ? ' checked' : '') + ' data-pk="' + pk + '"><span class="toggle-slider"></span></label>';
    visCell.querySelector('input[type="checkbox"]').addEventListener('change', function () {
      toggleVisibility(parseInt(this.dataset.pk), this);
    });
    row.dataset.stock = stock === 0 ? 'out' : stock <= threshold ? 'low' : 'in';
  }

  // Filters
  let searchTimer;
  document.getElementById('productSearch').addEventListener('input', function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilters, 250);
  });
  ['catFilter', 'stockFilter', 'visFilter'].forEach(id => {
    document.getElementById(id).addEventListener('change', applyFilters);
  });

  function applyFilters() {
    const q = document.getElementById('productSearch').value.toLowerCase().trim();
    const cat = document.getElementById('catFilter').value;
    const stk = document.getElementById('stockFilter').value;
    const vis = document.getElementById('visFilter').value;
    document.querySelectorAll('#productsTbody tr.p-row').forEach(row => {
      const match = (!q || row.dataset.name.includes(q) || row.dataset.sku.includes(q)) &&
                    (!cat || row.dataset.cat === cat) &&
                    (!stk || row.dataset.stock === stk) &&
                    (!vis || row.dataset.vis === vis);
      row.classList.toggle('hidden', !match);
    });
  }

  // Bulk select
  document.getElementById('selectAll').addEventListener('change', function () {
    document.querySelectorAll('.row-check').forEach(c => { c.checked = this.checked; });
    updateBulk();
  });
  document.querySelectorAll('.row-check').forEach(c => c.addEventListener('change', updateBulk));

  function updateBulk() {
    const checked = document.querySelectorAll('.row-check:checked');
    const bar = document.getElementById('bulkBar');
    document.getElementById('bulkCount').textContent = checked.length;
    bar.classList.toggle('visible', checked.length > 0);
    const all = document.querySelectorAll('.row-check');
    const selectAll = document.getElementById('selectAll');
    selectAll.indeterminate = checked.length > 0 && checked.length < all.length;
    selectAll.checked = checked.length === all.length && all.length > 0;
  }

  document.getElementById('btn-clear-selection').addEventListener('click', function () {
    document.querySelectorAll('.row-check, #selectAll').forEach(c => { c.checked = false; });
    updateBulk();
  });

  document.getElementById('btn-bulk-delete').addEventListener('click', bulkDelete);
  document.getElementById('btn-bulk-visible').addEventListener('click', () => bulkVisibility(true));
  document.getElementById('btn-bulk-hidden').addEventListener('click', () => bulkVisibility(false));

  function selectedPks() {
    return Array.from(document.querySelectorAll('.row-check:checked')).map(c => c.value);
  }

  function bulkDelete() {
    const pks = selectedPks();
    if (!pks.length || !confirm('Delete ' + pks.length + ' product(s)?')) return;
    fetch('/dashboard/products/bulk-delete/', {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
      body: JSON.stringify({ pks }),
    }).then(() => window.location.reload());
  }

  function bulkVisibility(visible) {
    const pks = selectedPks();
    if (!pks.length) return;
    fetch('/dashboard/products/bulk-visibility/', {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
      body: JSON.stringify({ pks, visible }),
    }).then(() => window.location.reload());
  }

  // Visibility toggle
  function toggleVisibility(pk, checkbox) {
    fetch('/dashboard/products/' + pk + '/toggle/', {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
    }).then(r => r.json()).then(data => {
      const row = document.querySelector('tr[data-pk="' + pk + '"]');
      if (row) row.dataset.vis = data.is_visible ? 'visible' : 'hidden';
      checkbox.checked = data.is_visible;
    }).catch(() => { checkbox.checked = !checkbox.checked; });
  }
  window.toggleVisibility = toggleVisibility;

  // Attach visibility toggles on initial load
  document.querySelectorAll('.vis-toggle').forEach(input => {
    input.addEventListener('change', function () {
      toggleVisibility(parseInt(this.dataset.pk), this);
    });
  });

  // Row click → product detail
  document.querySelectorAll('#productsTbody tr.p-row').forEach(row => {
    row.addEventListener('click', function (e) {
      if (e.target.closest('td[data-no-nav]')) return;
      window.location.href = '/dashboard/products/' + this.dataset.pk + '/';
    });
  });
});

// ── Dashboard product detail ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const editBtn = document.getElementById('editBtn');
  if (!editBtn) return;

  const CSRF = getCsrf();
  const PK = parseInt(document.getElementById('dashboard-root').dataset.pk);
  let specs = [];

  function enterEdit() {
    document.querySelectorAll('.view-mode').forEach(el => { el.style.display = 'none'; });
    document.querySelectorAll('.edit-mode').forEach(el => {
      if (el.classList.contains('edit-textarea')) el.style.display = 'block';
      else if (el.id === 'imgEditGrid') el.style.display = 'grid';
      else if (el.classList.contains('upload-zone')) el.style.display = 'block';
      else el.style.display = 'flex';
    });
    editBtn.style.display = 'none';
    document.getElementById('backBtn').style.display = 'none';
    document.getElementById('editBar').classList.add('visible');
    document.querySelector('.page-content').style.paddingTop = '52px';
    initSpecBuilder();
  }

  function cancelEdit() {
    document.querySelectorAll('.view-mode').forEach(el => { el.style.display = ''; });
    document.querySelectorAll('.edit-mode').forEach(el => { el.style.display = 'none'; });
    editBtn.style.display = '';
    document.getElementById('backBtn').style.display = '';
    document.getElementById('editBar').classList.remove('visible');
    document.querySelector('.page-content').style.paddingTop = '';
  }

  function submitEdit() { serializeSpecs(); document.getElementById('editForm').submit(); }

  editBtn.addEventListener('click', enterEdit);
  document.getElementById('btn-cancel-edit-top').addEventListener('click', cancelEdit);
  document.getElementById('btn-submit-edit-top').addEventListener('click', submitEdit);
  document.getElementById('btn-cancel-edit-bottom').addEventListener('click', cancelEdit);
  document.getElementById('btn-submit-edit-bottom').addEventListener('click', submitEdit);

  // Spec builder
  function initSpecBuilder() {
    specs = [];
    const raw = document.getElementById('dashboard-root').dataset.specs || '';
    if (raw) {
      raw.split('\n').forEach(line => {
        const idx = line.indexOf(':');
        if (idx > -1) specs.push({ k: line.slice(0, idx).trim(), v: line.slice(idx + 1).trim() });
      });
    }
    renderSpecs();
    document.getElementById('specVal').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); addSpec(); }
    });
  }

  function addSpec() {
    const k = document.getElementById('specKey').value.trim();
    const v = document.getElementById('specVal').value.trim();
    if (!k || !v) return;
    specs.push({ k, v });
    renderSpecs();
    document.getElementById('specKey').value = '';
    document.getElementById('specVal').value = '';
    document.getElementById('specKey').focus();
  }

  function removeSpec(i) { specs.splice(i, 1); renderSpecs(); }
  window.removeSpec = removeSpec; // called from dynamically built HTML

  function renderSpecs() {
    const c = document.getElementById('specTags');
    if (specs.length === 0) {
      c.innerHTML = '<span style="font-size:11px;color:var(--text-muted)">Specs will appear here…</span>';
      return;
    }
    c.innerHTML = specs.map((s, i) =>
      '<span class="spec-tag">' + s.k + ': ' + s.v +
      '<span class="spec-tag-del" data-idx="' + i + '">×</span></span>'
    ).join('');
    c.querySelectorAll('.spec-tag-del').forEach(el => {
      el.addEventListener('click', function () { removeSpec(parseInt(this.dataset.idx)); });
    });
  }

  function serializeSpecs() {
    document.getElementById('specsJson').value = JSON.stringify(specs);
  }

  document.getElementById('btn-add-spec').addEventListener('click', addSpec);

  // Flag toggles
  document.querySelectorAll('.flag-toggle').forEach(input => {
    input.addEventListener('change', function () {
      const field = this.dataset.field;
      const rowId = this.dataset.row;
      fetch('/dashboard/products/' + PK + '/flags/', {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
        body: JSON.stringify({ field }),
      }).then(r => r.json()).then(data => {
        document.getElementById(rowId).classList.toggle('on', data[field]);
        this.checked = data[field];
      }).catch(() => { this.checked = !this.checked; });
    });
  });

  // Image preview
  const newImagesInput = document.getElementById('newImagesInput');
  if (newImagesInput) {
    newImagesInput.addEventListener('change', function () {
      const grid = document.getElementById('newImagesPreview');
      grid.innerHTML = '';
      Array.from(this.files).forEach(f => {
        const url = URL.createObjectURL(f);
        const div = document.createElement('div');
        div.className = 'img-thumb';
        div.style.cssText = 'position:relative';
        const img = document.createElement('img');
        img.src = url;
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:6px;';
        div.appendChild(img);
        grid.appendChild(div);
      });
    });
  }

  // Set cover buttons
  document.querySelectorAll('.btn-set-cover').forEach(btn => {
    btn.addEventListener('click', function () {
      const imgId = parseInt(this.dataset.imgId);
      fetch('/dashboard/products/' + PK + '/set-cover/', {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_id: imgId }),
      }).then(() => window.location.reload());
    });
  });

  // Delete product
  const deleteBtn = document.getElementById('btn-delete-product');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', function () {
      const name = this.dataset.name;
      if (!confirm('Delete ' + name + '?')) return;
      const f = document.createElement('form');
      f.method = 'post';
      f.action = '/dashboard/products/' + PK + '/delete/';
      const c = document.createElement('input');
      c.type = 'hidden'; c.name = 'csrfmiddlewaretoken'; c.value = CSRF;
      f.appendChild(c);
      document.body.appendChild(f);
      f.submit();
    });
  }
});

// ── Dashboard order detail ────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const statusSelect = document.getElementById('statusSelect');
  if (!statusSelect) return;

  const CSRF = getCsrf();
  const root = document.getElementById('dashboard-root');
  const ORDER = root ? root.dataset.order : '';

  document.getElementById('btn-update-status').addEventListener('click', function () {
    const status = statusSelect.value;
    fetch('/dashboard/orders/' + ORDER + '/status/', {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'status=' + encodeURIComponent(status),
    }).then(r => r.json()).then(data => {
      if (data.label) {
        const badge = document.getElementById('statusBadge');
        badge.textContent = data.label;
        badge.className = 'status-badge s-' + data.status;
        const msg = document.getElementById('statusMsg');
        msg.style.display = 'block';
        setTimeout(() => { msg.style.display = 'none'; }, 2500);
      }
    });
  });

  document.getElementById('btn-add-note').addEventListener('click', function () {
    const body = document.getElementById('noteBody').value.trim();
    if (!body) return;
    fetch('/dashboard/orders/' + ORDER + '/note/', {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'body=' + encodeURIComponent(body),
    }).then(r => r.json()).then(data => {
      if (data.body) {
        const noNotes = document.getElementById('noNotes');
        if (noNotes) noNotes.remove();
        const list = document.getElementById('notesList');
        const el = document.createElement('div');
        el.className = 'note-entry';
        el.innerHTML = data.body + '<div class="note-meta">' + data.created_at + '</div>';
        list.insertBefore(el, list.firstChild);
        document.getElementById('noteBody').value = '';
      }
    });
  });
});

// ── Dashboard home: low stock scroll ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  const lowStockLink = document.getElementById('low-stock-scroll');
  if (lowStockLink) {
    lowStockLink.addEventListener('click', function () {
      const target = document.querySelector('.card:has(.low-stock-section)');
      if (target) target.scrollIntoView({ behavior: 'smooth' });
    });
  }
});
