// ==================================================
// auth.js — 집찾GO 로그인/회원가입 공통 스크립트
// member/auth.html 에서 사용 (login/signup 통합)
// ==================================================

document.addEventListener('DOMContentLoaded', () => {

  /* ---------- 로그인 후 이동할 목적지 (?redirect=...) ----------
     이 프로젝트는 정적 HTML 파일이 아니라 Thymeleaf 컨트롤러 라우팅을 쓰므로,
     기본 목적지는 파일 경로(index.html)가 아니라 실제 라우팅 경로(/)여야 함. */
  const params = new URLSearchParams(window.location.search);
  const redirectTarget = params.get('redirect') || '/';

  function goToRedirectTarget() {
    window.location.href = redirectTarget;
  }

  // 시연/발표용 게스트 모드 전용 플래그.
  // 서버 세션과는 완전히 별개로 동작해서, 네트워크가 불안정한 상황에서도
  // "무조건 로그인된 것처럼" 보여주기 위한 안전장치예요.
  // 실제 로그인/회원가입은 이 값을 절대 쓰지 않고, 서버 세션(/api/auth/check)만 기준으로 삼아요.
  function setGuestMode() {
    localStorage.setItem('jipchatgoGuestMode', 'true');
  }

  // 특정 페이지로 가기 위해 로그인이 필요해서 넘어온 경우, 안내 배너를 보여줘요.
  if (params.get('redirect')) {
    const banner = document.createElement('div');
    banner.className = 'redirect-notice';
    const isRegister = redirectTarget.includes('/property/register');
    banner.innerHTML = `<i class="ti ti-info-circle"></i> ${
      isRegister ? '매물을 등록하려면 먼저 로그인해주세요.' : '계속하려면 먼저 로그인해주세요.'
    }`;
    const tabs = document.querySelector('.auth-tabs');
    if (tabs) tabs.insertAdjacentElement('beforebegin', banner);
  }

  /* ---------- 헤더 스크롤 / 모바일 메뉴 (common.css 공통 헤더용) ---------- */
  const header = document.getElementById('mainHeader');
  if (header) {
    window.addEventListener('scroll', () => {
      header.classList.toggle('scrolled', window.scrollY > 20);
    });
  }
  const menuBtn = document.getElementById('menuBtn');
  const mobileNav = document.getElementById('mobileNav');
  if (menuBtn && mobileNav) {
    menuBtn.addEventListener('click', () => {
      menuBtn.classList.toggle('active');
      mobileNav.classList.toggle('active');
    });
  }

  /* ---------- 탭 전환 (로그인 ↔ 회원가입) ---------- */
  const tabs = document.querySelectorAll('.auth-tab');
  const forms = document.querySelectorAll('.auth-form');
  const visualCopy = {
    login: {
      eyebrow: '로그인',
      title: 'AI가 추천하는 내 집,<br>로그인하고 이어가세요',
      desc: '저장해 둔 조건과 관심 매물을 그대로 불러와 드려요.'
    },
    signup: {
      eyebrow: '회원가입',
      title: '몇 분이면 충분해요,<br>지금 시작하는 부동산 여정',
      desc: '일반회원과 공인중개사 모두 집찾GO에서 시작할 수 있어요.'
    }
  };

  function switchTab(name) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    forms.forEach(f => f.classList.toggle('active', f.dataset.form === name));

    const eyebrowEl = document.querySelector('.visual-copy .eyebrow');
    const titleEl = document.querySelector('.visual-copy h2');
    const descEl = document.querySelector('.visual-copy p');
    const copy = visualCopy[name];
    if (copy && eyebrowEl && titleEl && descEl) {
      [eyebrowEl, titleEl, descEl].forEach(el => el.style.opacity = 0);
      setTimeout(() => {
        eyebrowEl.textContent = copy.eyebrow;
        titleEl.innerHTML = copy.title;
        descEl.textContent = copy.desc;
        [eyebrowEl, titleEl, descEl].forEach(el => el.style.opacity = 1);
      }, 150);
    }

    updateKeyring(name);
    history.replaceState(null, '', name === 'signup' ? '#signup' : '#login');
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
  document.querySelectorAll('[data-switch-to]').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.switchTo));
  });

  // URL 해시로 초기 탭 결정 (#signup 이면 회원가입 탭부터)
  if (location.hash === '#signup' || document.body.dataset.defaultTab === 'signup') {
    switchTab('signup');
  } else {
    switchTab('login');
  }

  /* ---------- 시그니처: 진행 단계에 따라 채워지는 열쇠고리 ---------- */
  function updateKeyring(name) {
    const keys = document.querySelectorAll('.keyring .key');
    if (!keys.length) return;
    const filledCount = name === 'signup' ? getSignupProgress() : 1;
    keys.forEach((key, i) => key.classList.toggle('filled', i < filledCount));
  }

  function getSignupProgress() {
    const name = document.getElementById('suName');
    const email = document.getElementById('suEmail');
    const pw = document.getElementById('suPassword');
    let count = 0;
    if (name && name.value.trim()) count++;
    if (email && email.value.trim()) count++;
    if (pw && pw.value.trim()) count++;
    return count;
  }

  ['suName', 'suEmail', 'suPassword'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => updateKeyring('signup'));
  });

  /* ---------- 비밀번호 보이기/숨기기 ---------- */
  document.querySelectorAll('.toggle-visibility').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      if (!input) return;
      const isPw = input.type === 'password';
      input.type = isPw ? 'text' : 'password';
      btn.innerHTML = isPw ? '<i class="ti ti-eye-off"></i>' : '<i class="ti ti-eye"></i>';
    });
  });

  /* ---------- 회원 유형 선택 (일반회원 / 공인중개사) ---------- */
  const typeCards = document.querySelectorAll('.type-card');
  const brokerFields = document.getElementById('brokerFields');
  typeCards.forEach(card => {
    card.addEventListener('click', () => {
      typeCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      card.querySelector('input').checked = true;
      if (brokerFields) {
        brokerFields.classList.toggle('show', card.dataset.type === 'broker');
      }
    });
  });

  /* ---------- 전체 동의 체크박스 ---------- */
  const agreeAll = document.getElementById('agreeAll');
  const agreeItems = document.querySelectorAll('.agree-item');
  if (agreeAll) {
    agreeAll.addEventListener('change', () => {
      agreeItems.forEach(item => { item.checked = agreeAll.checked; });
    });
    agreeItems.forEach(item => {
      item.addEventListener('change', () => {
        agreeAll.checked = Array.from(agreeItems).every(i => i.checked);
      });
    });
  }

  /* ---------- 간단한 유효성 검사 ---------- */
  function validateEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  /* ---------- 로그인: 실제 서버 API 연결 ---------- */
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('loginEmail');
      const pw = document.getElementById('loginPassword');
      let ok = true;
      if (!validateEmail(email.value)) { email.classList.add('invalid'); ok = false; }
      else email.classList.remove('invalid');
      if (pw.value.length < 4) { pw.classList.add('invalid'); ok = false; }
      else pw.classList.remove('invalid');
      if (!ok) return;

      const submitBtn = loginForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.value, password: pw.value })
        });
        const data = await res.json();

        if (data.success) {
          showToast(`${data.name}님, 로그인 되었습니다.`);
          setTimeout(goToRedirectTarget, 700);
        } else {
          showToast(data.message || '로그인에 실패했어요.');
        }
      } catch (err) {
        showToast('서버에 연결할 수 없어요. 잠시 후 다시 시도해주세요.');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  /* ---------- 회원가입: 실제 서버 API 연결 (일반회원 전용) ---------- */
  const signupForm = document.getElementById('signupForm');
  if (signupForm) {
    signupForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pw = document.getElementById('suPassword');
      const pwCheck = document.getElementById('suPasswordCheck');
      const requiredAgree = document.querySelectorAll('.agree-item[required]');
      let ok = true;

      if (pw.value.length < 8) { pw.classList.add('invalid'); ok = false; }
      else pw.classList.remove('invalid');

      if (pwCheck.value !== pw.value || !pwCheck.value) { pwCheck.classList.add('invalid'); ok = false; }
      else pwCheck.classList.remove('invalid');

      requiredAgree.forEach(chk => { if (!chk.checked) ok = false; });

      if (!ok) {
        if (!Array.from(requiredAgree).every(c => c.checked)) {
          showToast('필수 약관에 동의해주세요.');
        }
        return;
      }

      // 공인중개사 가입은 아직 서버에서 지원하지 않음 (일반회원만 우선 연결)
      const selectedType = document.querySelector('input[name="memberType"]:checked');
      if (selectedType && selectedType.value === 'broker') {
        showToast('공인중개사 회원가입은 아직 준비 중이에요. 곧 지원할게요!');
        return;
      }

      const suName = document.getElementById('suName');
      const suEmail = document.getElementById('suEmail');
      const suPhone = document.getElementById('suPhone');

      const submitBtn = signupForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      try {
        const res = await fetch('/api/auth/signup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: suEmail.value,
            password: pw.value,
            name: suName.value,
            phone: suPhone.value
          })
        });
        const data = await res.json();

        if (data.success) {
          showToast('회원가입이 완료됐어요. 환영합니다!');
          setTimeout(goToRedirectTarget, 700);
        } else {
          showToast(data.message || '회원가입에 실패했어요.');
        }
      } catch (err) {
        showToast('서버에 연결할 수 없어요. 잠시 후 다시 시도해주세요.');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  /* ---------- 게스트 체험 로그인 (발표/시연용, 서버와 무관하게 동작) ---------- */
  document.querySelectorAll('.guest-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setGuestMode();
      showToast('게스트 모드로 접속했어요 (시연용 계정)');
      setTimeout(goToRedirectTarget, 900);
    });
  });

  /* ---------- 토스트 ---------- */
  function showToast(message) {
    let toast = document.querySelector('.toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'toast';
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toast.classList.remove('show'), 2400);
  }

  /* ---------- Back to Top FAB ---------- */
  const backToTop = document.getElementById('backToTop');
  if (backToTop) {
    window.addEventListener('scroll', () => {
      backToTop.classList.toggle('show', window.scrollY > 400);
    });
    backToTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
});
