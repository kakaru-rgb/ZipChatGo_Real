// ==================================================
// admin.js — 집찾GO 관리자 매물 검수 페이지
// ==================================================

document.addEventListener('DOMContentLoaded', () => {

  const tabs = document.querySelectorAll('.admin-tab');
  const tbody = document.getElementById('propertyTableBody');
  const emptyState = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const countPendingEl = document.getElementById('countPending');

  const detailPanel = document.getElementById('detailPanel');
  const detailBackdrop = document.getElementById('detailBackdrop');
  const detailContent = document.getElementById('detailContent');
  const detailClose = document.getElementById('detailClose');

  let currentStatus = 'PENDING';
  let currentItems = [];

  /* ---------- 탭 전환 ---------- */
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('is-active'));
      tab.classList.add('is-active');
      currentStatus = tab.dataset.status;
      loadList(currentStatus);
    });
  });

  /* ---------- 대기중 개수 뱃지 (처음 로드시 한 번) ---------- */
  async function refreshPendingCount() {
    try {
      const res = await fetch('/api/admin/properties?status=PENDING');
      const data = await res.json();
      countPendingEl.textContent = data.length;
    } catch (err) {
      // 조용히 무시 (뱃지는 부가 정보라 실패해도 페이지 동작엔 지장 없음)
    }
  }

  /* ---------- 목록 조회 ---------- */
  async function loadList(status) {
    tbody.innerHTML = '';
    emptyState.hidden = true;
    loadingState.hidden = false;

    try {
      const res = await fetch('/api/admin/properties?status=' + encodeURIComponent(status));
      if (res.status === 401 || res.status === 403) {
        alert('관리자만 접근할 수 있어요.');
        window.location.href = '/';
        return;
      }
      const items = await res.json();
      currentItems = items;
      loadingState.hidden = true;

      if (items.length === 0) {
        emptyState.hidden = false;
        return;
      }

      items.forEach(item => tbody.appendChild(buildRow(item)));
    } catch (err) {
      loadingState.textContent = '목록을 불러오지 못했어요. 새로고침해주세요.';
    }
  }

  /* ---------- 행 렌더링 ---------- */
  function buildRow(item) {
    const p = item.property;
    const tr = document.createElement('tr');

    tr.innerHTML = `
      <td class="cell-property">
        <strong>${escapeHtml(p.propertyType || '')} · ${escapeHtml(p.dealType || '')}</strong>
        <span>${escapeHtml(p.address1 || '')}</span>
      </td>
      <td>${p.area != null ? p.area + '㎡' : '-'} / ${escapeHtml(p.floorInfo || '-')} · 방${p.rooms ?? '-'}/욕실${p.baths ?? '-'}</td>
      <td>${formatPrice(p)}</td>
      <td class="cell-registrant">
        <span class="registrant-name">${escapeHtml(item.registrantName || '')}</span>
        <span class="registrant-email">${escapeHtml(item.registrantEmail || '')}</span>
      </td>
      <td>${formatDate(p.createdAt)}</td>
      <td><span class="status-badge ${p.status}">${statusLabel(p.status)}</span></td>
      <td class="col-actions"></td>
    `;

    tr.addEventListener('click', () => openDetail(item));

    // 대기중 탭에서만 목록에서 바로 승인/거절 버튼 노출
    if (p.status === 'PENDING') {
      const actionsCell = tr.querySelector('.col-actions');
      const wrap = document.createElement('div');
      wrap.className = 'row-actions';

      const approveBtn = document.createElement('button');
      approveBtn.className = 'btn-approve';
      approveBtn.textContent = '승인';
      approveBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        handleDecision(p.id, 'approve');
      });

      const rejectBtn = document.createElement('button');
      rejectBtn.className = 'btn-reject';
      rejectBtn.textContent = '거절';
      rejectBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        handleDecision(p.id, 'reject');
      });

      wrap.appendChild(approveBtn);
      wrap.appendChild(rejectBtn);
      actionsCell.appendChild(wrap);
    }

    return tr;
  }

  /* ---------- 상세 패널 ---------- */
  function openDetail(item) {
    const p = item.property;

    const attributes = p.attributes || [];
    const tags = attributes.filter(a => a.category === 'TAG');
    const options = attributes.filter(a => a.category === 'OPTION');
    const utilities = attributes.filter(a => a.category === 'UTILITY');

    const transit = safeParseJson(p.transitInfo);
    const school = safeParseJson(p.schoolInfo);

    const nameMismatch = item.registrantName &&
      p.ownerName &&
      item.registrantName.trim() !== p.ownerName.trim();

    detailContent.innerHTML = `
      <div class="detail-photo-placeholder">
        <i class="ti ti-photo"></i>
        사진 준비 중
      </div>

      <div class="detail-title">${escapeHtml(p.propertyType || '')} · ${escapeHtml(p.dealType || '')}</div>
      <div class="detail-subtitle">${escapeHtml(p.address1 || '')} ${escapeHtml(p.address2 || '')}</div>

      <div class="detail-section">
        <h3>기본 정보</h3>
        <dl class="detail-grid">
          <div><dt>가격</dt><dd>${formatPrice(p)}</dd></div>
          <div><dt>면적</dt><dd>${p.area != null ? p.area + '㎡' : '-'}</dd></div>
          <div><dt>층수</dt><dd>${escapeHtml(p.floorInfo || '-')}</dd></div>
          <div><dt>방/욕실</dt><dd>${p.rooms ?? '-'} / ${p.baths ?? '-'}</dd></div>
          <div><dt>관리비</dt><dd>${p.maintenanceFee != null ? p.maintenanceFee + '만원' : '-'}</dd></div>
          <div><dt>기타관리비</dt><dd>${escapeHtml(p.etcFee || '-')}</dd></div>
        </dl>
      </div>

      ${tags.length ? `
      <div class="detail-section">
        <h3>특징</h3>
        <div class="pill-group">${tags.map(t => `<span class="pill">${escapeHtml(t.value)}</span>`).join('')}</div>
      </div>` : ''}

      ${options.length ? `
      <div class="detail-section">
        <h3>옵션</h3>
        <div class="pill-group">${options.map(t => `<span class="pill">${escapeHtml(t.value)}</span>`).join('')}</div>
      </div>` : ''}

      ${utilities.length ? `
      <div class="detail-section">
        <h3>관리비 포함 항목</h3>
        <div class="pill-group">${utilities.map(t => `<span class="pill">${escapeHtml(t.value)}</span>`).join('')}</div>
      </div>` : ''}

      <div class="detail-section">
        <h3>교통 / 학군 (등록 시점 자동계산)</h3>
        <dl class="detail-grid">
          <div><dt>지하철</dt><dd>${escapeHtml(transit?.subway || '-')}</dd></div>
          <div><dt>버스</dt><dd>${Array.isArray(transit?.bus) ? escapeHtml(transit.bus.join(', ')) : '-'}</dd></div>
          <div><dt>초등학교</dt><dd>${escapeHtml(school?.elementary || '-')}</dd></div>
          <div><dt>중학교</dt><dd>${escapeHtml(school?.middle || '-')}</dd></div>
        </dl>
      </div>

      <div class="detail-section">
        <h3>등록자 / 집주인 정보</h3>
        <dl class="detail-grid">
          <div><dt>등록 회원</dt><dd>${escapeHtml(item.registrantName || '-')}</dd></div>
          <div><dt>회원 이메일</dt><dd>${escapeHtml(item.registrantEmail || '-')}</dd></div>
          <div><dt>집주인 이름</dt><dd>${escapeHtml(p.ownerName || '-')}</dd></div>
          <div><dt>집주인 연락처</dt><dd>${escapeHtml(p.ownerPhone || '-')}</dd></div>
        </dl>
        ${nameMismatch ? `
        <div class="owner-warning">
          <i class="ti ti-alert-triangle"></i>
          <span>집주인 이름이 등록 회원의 실명과 달라요. 실제 소유자가 맞는지 확인이 필요해요.</span>
        </div>` : ''}
      </div>

      ${p.status === 'PENDING' ? `
      <div class="detail-actions">
        <button type="button" class="btn-reject-lg" id="detailRejectBtn">거절</button>
        <button type="button" class="btn-approve-lg" id="detailApproveBtn">승인</button>
      </div>` : ''}
    `;

    if (p.status === 'PENDING') {
      document.getElementById('detailApproveBtn').addEventListener('click', () => handleDecision(p.id, 'approve', true));
      document.getElementById('detailRejectBtn').addEventListener('click', () => handleDecision(p.id, 'reject', true));
    }

    detailPanel.classList.add('is-open');
    detailBackdrop.hidden = false;
    requestAnimationFrame(() => detailBackdrop.classList.add('is-visible'));
    detailPanel.setAttribute('aria-hidden', 'false');
  }

  function closeDetail() {
    detailPanel.classList.remove('is-open');
    detailBackdrop.classList.remove('is-visible');
    detailPanel.setAttribute('aria-hidden', 'true');
    setTimeout(() => { detailBackdrop.hidden = true; }, 250);
  }

  detailClose.addEventListener('click', closeDetail);
  detailBackdrop.addEventListener('click', closeDetail);

  /* ---------- 승인/거절 처리 ---------- */
  async function handleDecision(propertyId, action, closeAfter) {
    try {
      const res = await fetch(`/api/admin/properties/${propertyId}/${action}`, { method: 'POST' });
      const data = await res.json();

      if (!data.success) {
        alert(data.message || '처리 중 문제가 발생했어요.');
        return;
      }

      if (closeAfter) closeDetail();
      loadList(currentStatus);
      refreshPendingCount();
    } catch (err) {
      alert('서버에 연결할 수 없어요.');
    }
  }

  /* ---------- 유틸 ---------- */
  function statusLabel(status) {
    if (status === 'PENDING') return '대기중';
    if (status === 'APPROVED') return '승인됨';
    if (status === 'REJECTED') return '거절됨';
    return status;
  }

  function formatPrice(p) {
    if (p.dealType === '매매') return p.price != null ? p.price + '만원' : '-';
    if (p.dealType === '전세') return p.deposit != null ? '전세 ' + p.deposit + '만원' : '-';
    if (p.dealType === '월세') return (p.deposit != null && p.monthly != null) ? `월세 ${p.deposit}/${p.monthly}` : '-';
    return '-';
  }

  function formatDate(value) {
    if (!value) return '-';
    return value.replace('T', ' ').slice(0, 16);
  }

  function safeParseJson(value) {
    if (!value) return null;
    try { return JSON.parse(value); } catch (e) { return null; }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ---------- 초기 로드 ---------- */
  loadList(currentStatus);
  refreshPendingCount();
});
