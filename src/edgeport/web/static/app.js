// EdgePort Web Inspector Client Logic
document.addEventListener('DOMContentLoaded', () => {
  const elements = {
    statusDot: document.getElementById('status-dot'),
    statusText: document.getElementById('status-text'),
    publicUrl: document.getElementById('meta-public-url'),
    targetUrl: document.getElementById('meta-target-url'),
    requestCount: document.getElementById('request-count'),
    requestList: document.getElementById('request-list'),
    emptyState: document.getElementById('empty-state'),
    filterInput: document.getElementById('filter-input'),
    detailPlaceholder: document.getElementById('detail-placeholder'),
    detailContent: document.getElementById('detail-content'),
    detailMethod: document.getElementById('detail-method'),
    detailPath: document.getElementById('detail-path'),
    detailStatus: document.getElementById('detail-status'),
    detailDuration: document.getElementById('detail-duration'),
    detailProvider: document.getElementById('detail-provider'),
    viewReqBody: document.getElementById('view-req-body'),
    viewReqHeaders: document.getElementById('view-req-headers').querySelector('tbody'),
    viewRespBody: document.getElementById('view-resp-body'),
    viewRespHeaders: document.getElementById('view-resp-headers').querySelector('tbody'),
    btnCopyCurl: document.getElementById('btn-copy-curl'),
    btnReplay: document.getElementById('btn-replay'),
    btnEditReplay: document.getElementById('btn-edit-replay'),
    btnClearTraffic: document.getElementById('btn-clear-traffic'),
    btnShowQr: document.getElementById('btn-show-qr'),
    btnExportHar: document.getElementById('btn-export-har'),
    btnExportPostman: document.getElementById('btn-export-postman'),
    modalQr: document.getElementById('modal-qr'),
    btnCloseQr: document.getElementById('btn-close-qr'),
    qrModalUrl: document.getElementById('qr-modal-url'),
    qrImage: document.getElementById('qr-image'),
    modalEditReplay: document.getElementById('modal-edit-replay'),
    btnCloseEdit: document.getElementById('btn-close-edit'),
    btnCancelEdit: document.getElementById('btn-cancel-edit'),
    btnSubmitEditReplay: document.getElementById('btn-submit-edit-replay'),
    editReqBody: document.getElementById('edit-req-body'),
    editWebhookSecret: document.getElementById('edit-webhook-secret'),
    tabButtons: document.querySelectorAll('.tab-btn'),
    tabPanes: document.querySelectorAll('.tab-pane'),
    toastContainer: document.getElementById('toast-container'),
  };

  let transactions = [];
  let currentTransactionId = null;
  let currentTransactionDetail = null;
  let currentCurl = '';

  // 1. Fetch Tunnel Info
  async function fetchInfo() {
    try {
      const res = await fetch('/api/info');
      const data = await res.json();
      if (data.public_url) {
        elements.publicUrl.href = data.public_url;
        elements.publicUrl.textContent = data.public_url;
        elements.statusText.textContent = 'Online';
        elements.statusDot.classList.add('live');
        if (elements.qrModalUrl) elements.qrModalUrl.value = data.public_url;
      } else {
        elements.statusText.textContent = 'Disconnected';
        elements.statusDot.classList.remove('live');
      }
      if (data.target_url) {
        elements.targetUrl.textContent = data.target_url;
      }
    } catch (e) {
      console.error('Failed to fetch tunnel info', e);
    }
  }

  // 2. Fetch Initial Transactions
  async function fetchTransactions() {
    try {
      const res = await fetch('/api/transactions');
      const data = await res.json();
      transactions = data.transactions || [];
      renderList();
    } catch (e) {
      console.error('Failed to fetch transactions', e);
    }
  }

  // 3. Render Request List
  function renderList() {
    const filter = elements.filterInput.value.toLowerCase().trim();
    const filtered = transactions.filter(t => {
      if (!filter) return true;
      return t.path.toLowerCase().includes(filter) ||
             t.status.toString().includes(filter) ||
             t.method.toLowerCase().includes(filter);
    });

    elements.requestCount.textContent = transactions.length;

    if (filtered.length === 0) {
      elements.requestList.innerHTML = '';
      elements.requestList.appendChild(elements.emptyState);
      elements.emptyState.classList.remove('hidden');
      return;
    }

    elements.emptyState.classList.add('hidden');
    elements.requestList.innerHTML = '';

    filtered.slice().reverse().forEach(t => {
      const item = document.createElement('div');
      item.className = `request-item ${t.id === currentTransactionId ? 'active' : ''}`;
      item.onclick = () => selectTransaction(t.id);

      const statusGroup = Math.floor(t.status / 100);
      const providerBadge = t.provider ? `<span class="provider-badge">${escapeHtml(t.provider)}</span>` : '';

      item.innerHTML = `
        <div class="req-left">
          <span class="method-pill method-${t.method}">${escapeHtml(t.method)}</span>
          <span class="req-path" title="${escapeHtml(t.path)}">${escapeHtml(t.path)}</span>
        </div>
        <div class="req-right">
          ${providerBadge}
          <span class="status-pill status-${statusGroup}xx">${t.status}</span>
          <span class="latency-pill">${t.duration_ms}ms</span>
        </div>
      `;
      elements.requestList.appendChild(item);
    });
  }

  // 4. Select and View Transaction
  async function selectTransaction(id) {
    currentTransactionId = id;
    renderList();

    try {
      const res = await fetch(`/api/transactions/${id}`);
      const t = await res.json();
      if (t.error) return;

      currentTransactionDetail = t;
      currentCurl = t.curl_command || '';

      elements.detailPlaceholder.classList.add('hidden');
      elements.detailContent.classList.remove('hidden');

      elements.detailMethod.textContent = t.method;
      elements.detailMethod.className = `method-pill method-${t.method}`;
      elements.detailPath.textContent = t.full_url;

      const statusGroup = Math.floor(t.response_status / 100);
      elements.detailStatus.textContent = t.response_status;
      elements.detailStatus.className = `status-pill status-${statusGroup}xx`;

      elements.detailDuration.textContent = `${t.duration_ms}ms`;

      if (t.provider) {
        elements.detailProvider.textContent = t.provider;
        elements.detailProvider.classList.remove('hidden');
      } else {
        elements.detailProvider.classList.add('hidden');
      }

      elements.viewReqBody.textContent = t.request_body || '<empty body>';
      elements.viewRespBody.textContent = t.response_body || '<empty body>';

      renderTable(elements.viewReqHeaders, t.request_headers);
      renderTable(elements.viewRespHeaders, t.response_headers);

    } catch (e) {
      console.error('Failed to load transaction detail', e);
    }
  }

  function renderTable(tbody, headersObj) {
    tbody.innerHTML = '';
    if (!headersObj || Object.keys(headersObj).length === 0) {
      tbody.innerHTML = '<tr><td colspan="2" style="color: var(--text-muted);">No headers</td></tr>';
      return;
    }
    for (const [k, v] of Object.entries(headersObj)) {
      const row = document.createElement('tr');
      row.innerHTML = `<td>${escapeHtml(k)}</td><td>${escapeHtml(v)}</td>`;
      tbody.appendChild(row);
    }
  }

  // 5. Replay Action
  elements.btnReplay.onclick = async () => {
    if (!currentTransactionId) return;

    elements.btnReplay.disabled = true;
    elements.btnReplay.innerHTML = '<span class="btn-icon">⏳</span> Replaying...';

    try {
      const res = await fetch(`/api/transactions/${currentTransactionId}/replay`, { method: 'POST' });
      const result = await res.json();
      if (result.error) {
        showToast(`Replay failed: ${result.error}`);
      } else {
        showToast(`Replayed! Status: ${result.new_status} (${result.duration_ms}ms)`);
        await fetchTransactions();
        if (result.replayed_id) {
          selectTransaction(result.replayed_id);
        }
      }
    } catch (e) {
      showToast(`Replay error: ${e.message}`);
    } finally {
      elements.btnReplay.disabled = false;
      elements.btnReplay.innerHTML = '<span class="btn-icon">↻</span> Replay Request';
    }
  };

  // 6. Edit & Replay Modal
  elements.btnEditReplay.onclick = () => {
    if (!currentTransactionDetail) return;
    elements.editReqBody.value = currentTransactionDetail.request_body || '';
    elements.editWebhookSecret.value = '';
    elements.modalEditReplay.classList.remove('hidden');
  };

  elements.btnCloseEdit.onclick = () => elements.modalEditReplay.classList.add('hidden');
  elements.btnCancelEdit.onclick = () => elements.modalEditReplay.classList.add('hidden');

  elements.btnSubmitEditReplay.onclick = async () => {
    if (!currentTransactionId) return;

    elements.btnSubmitEditReplay.disabled = true;
    elements.btnSubmitEditReplay.textContent = 'Executing...';

    const payload = {
      override_body: elements.editReqBody.value,
      webhook_secret: elements.editWebhookSecret.value.trim() || undefined,
    };

    try {
      const res = await fetch(`/api/transactions/${currentTransactionId}/replay`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const result = await res.json();
      if (result.error) {
        showToast(`Edit & Replay failed: ${result.error}`);
      } else {
        showToast(`Replayed modified payload! Status: ${result.new_status}`);
        elements.modalEditReplay.classList.add('hidden');
        await fetchTransactions();
        if (result.replayed_id) {
          selectTransaction(result.replayed_id);
        }
      }
    } catch (e) {
      showToast(`Replay error: ${e.message}`);
    } finally {
      elements.btnSubmitEditReplay.disabled = false;
      elements.btnSubmitEditReplay.textContent = 'Execute Replay';
    }
  };

  // 7. QR Code Modal
  elements.btnShowQr.onclick = () => {
    elements.qrImage.src = `/api/qrcode?t=${Date.now()}`;
    elements.qrModalUrl.value = elements.publicUrl.href || '';
    elements.modalQr.classList.remove('hidden');
  };

  elements.btnCloseQr.onclick = () => {
    elements.modalQr.classList.add('hidden');
  };

  // 8. Export HAR and Postman
  elements.btnExportHar.onclick = () => {
    window.location.href = '/api/export/har';
    showToast('Exporting HAR 1.2 traffic archive...');
  };

  elements.btnExportPostman.onclick = () => {
    window.location.href = '/api/export/postman';
    showToast('Exporting Postman v2.1 collection...');
  };

  // 9. Copy cURL Action
  elements.btnCopyCurl.onclick = () => {
    if (!currentCurl) return;
    navigator.clipboard.writeText(currentCurl).then(() => {
      showToast('Copied cURL command to clipboard!');
    }).catch(() => {
      showToast('Failed to copy to clipboard');
    });
  };

  // 10. Clear Traffic
  elements.btnClearTraffic.onclick = () => {
    transactions = [];
    currentTransactionId = null;
    currentTransactionDetail = null;
    currentCurl = '';
    elements.detailContent.classList.add('hidden');
    elements.detailPlaceholder.classList.remove('hidden');
    renderList();
    showToast('Cleared traffic display');
  };

  // 11. Tabs Switcher
  elements.tabButtons.forEach(btn => {
    btn.onclick = () => {
      elements.tabButtons.forEach(b => b.classList.remove('active'));
      elements.tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetId = `tab-${btn.getAttribute('data-tab')}`;
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');
    };
  });

  // 12. Filter Input
  elements.filterInput.oninput = () => renderList();

  // 13. Server-Sent Events (SSE) Stream
  function connectSSE() {
    const eventSource = new EventSource('/events');

    eventSource.addEventListener('transaction', (event) => {
      const data = JSON.parse(event.data);
      transactions.push(data);
      renderList();
      if (!currentTransactionId) {
        selectTransaction(data.id);
      }
    });

    eventSource.onerror = () => {
      console.warn('SSE stream disconnected, reconnecting in 3s...');
      eventSource.close();
      setTimeout(connectSSE, 3000);
    };
  }

  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 300);
    }, 2500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Initial Boot
  fetchInfo();
  fetchTransactions();
  connectSSE();
});
