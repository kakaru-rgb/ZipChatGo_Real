/* ==========================================================
   register.js
   매물 등록 페이지(register.html) 전용 스크립트
   - 원래 register.html 안에 있던 두 개의 인라인 <script>를
     하나로 합쳐 분리한 파일이에요. 기존 동작/순서는 그대로 유지했어요.
   ========================================================== */

  // 헤더 스크롤 효과
  const header = document.getElementById('mainHeader');
  window.addEventListener('scroll', () => {
    header.classList.toggle('scrolled', window.scrollY > 20);
  });

  // 모바일 메뉴
  const menuBtn = document.getElementById('menuBtn');
  const topNav = document.getElementById('topNav');
  menuBtn.addEventListener('click', () => {
    menuBtn.classList.toggle('active');
    topNav.classList.toggle('active');
  });

  // ---------- 칩(라디오/체크박스) 선택 UI ----------
  function bindChip(chip) {
    const input = chip.querySelector('input');
    chip.addEventListener('click', (e) => {
      if (e.target.closest('.chip-remove')) return; // 삭제 버튼 클릭 시 선택 토글 방지
      if (input.type === 'radio') {
        document.querySelectorAll(`input[name="${input.name}"]`).forEach(i => {
          i.closest('.chip').classList.remove('selected');
        });
        input.checked = true;
        chip.classList.add('selected');
      } else {
        input.checked = !input.checked;
        chip.classList.toggle('selected', input.checked);
      }
      // 프로그래밍적으로 checked를 바꾸면 change 이벤트가 자동으로 발생하지 않으므로 직접 발생시켜요.
      input.dispatchEvent(new Event('change', { bubbles: true }));
      updatePreview();
    });
  }
  document.querySelectorAll('.chip').forEach(bindChip);

  // ---------- 사용자 정의 태그/옵션 추가 (공용 함수) ----------
  function setupCustomChipAdder({ gridEl, inputEl, btnEl, maxCount, duplicateMsg, limitMsg }) {
    if (!gridEl || !inputEl || !btnEl) return;
    let count = 0;

    function add() {
      const value = inputEl.value.trim();
      if (!value) return;

      if (count >= maxCount) {
        alert(limitMsg);
        return;
      }
      const exists = Array.from(gridEl.querySelectorAll('input')).some(
        i => i.value.toLowerCase() === value.toLowerCase()
      );
      if (exists) {
        alert(duplicateMsg);
        return;
      }

      const chip = document.createElement('label');
      chip.className = 'chip chip-custom selected';
      chip.innerHTML = `
        <input type="checkbox" value="${value}" checked>
        ${value}
        <span class="chip-remove" title="삭제"><i class="fa-solid fa-xmark"></i></span>
      `;
      gridEl.appendChild(chip);
      bindChip(chip);

      chip.querySelector('.chip-remove').addEventListener('click', () => {
        chip.remove();
        count--;
        updatePreview();
      });

      count++;
      inputEl.value = '';
      updatePreview();
    }

    btnEl.addEventListener('click', add);
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        add();
      }
    });
  }

  setupCustomChipAdder({
    gridEl: document.getElementById('tagGrid'),
    inputEl: document.getElementById('customTagInput'),
    btnEl: document.getElementById('customTagAdd'),
    maxCount: 5,
    duplicateMsg: '이미 추가된 특징이에요.',
    limitMsg: '직접 추가할 수 있는 특징은 최대 5개예요.'
  });

  setupCustomChipAdder({
    gridEl: document.getElementById('optionGrid'),
    inputEl: document.getElementById('customOptionInput'),
    btnEl: document.getElementById('customOptionAdd'),
    maxCount: 5,
    duplicateMsg: '이미 추가된 옵션이에요.',
    limitMsg: '직접 추가할 수 있는 옵션은 최대 5개예요.'
  });

  // ---------- 카카오맵 연동: 지오코딩 / 검색 / 지도 / 학군 자동 매칭 ----------
  let zoneData = { elementary: [], middle: [], high: [] };
  let kakaoMap = null;
  let kakaoMarker = null;
  let kakaoZoneOverlays = [];
  let kakaoGeocoder = null;
  let currentSchoolMatch = null; // 1단계에서 확정된 학군 매칭 결과 (모달에서도 재사용)

  // 카카오 SDK는 autoload=false로 불러왔기 때문에 직접 load()를 호출해줘야 해요.
  if (typeof kakao !== 'undefined' && kakao.maps) {
    kakao.maps.load(() => {
      kakaoGeocoder = new kakao.maps.services.Geocoder();
    });
  } else {
    console.error('[카카오맵] SDK를 불러오지 못했어요. appkey와 도메인 등록을 확인해주세요.');
  }

  // 학군 데이터 로드 (분당구)
  Promise.all([
    fetch('../../static/data/elementary_zones_bundang.json').then(r => r.json()).catch(() => []),
    fetch('../../static/data/middle_zones_bundang.json').then(r => r.json()).catch(() => []),
    fetch('../../static/data/high_zones_seongnam.json').then(r => r.json()).catch(() => [])
  ]).then(([el, mid, high]) => {
    zoneData = { elementary: el, middle: mid, high: high };
  });

  let transitData = { subway: [], bus: [] };
  fetch('../../static/data/transit_points_bundang.json').then(r => r.json()).then(d => {
    transitData = d;
  }).catch(() => {});

  // ---------- 두 좌표 사이 직선거리 (m) — Haversine ----------
  function distanceMeters(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180;
    const dp = (lat2 - lat1) * Math.PI / 180;
    const dl = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    return Math.round(2 * R * Math.asin(Math.sqrt(a)));
  }

  // ---------- 주소 → 좌표가 확정되면 가까운 지하철역·버스정류장 찾기 ----------
  function matchNearbyTransit(lng, lat) {
    const withDist = (list, type) => list
      .map(p => ({ ...p, type, distance: distanceMeters(lat, lng, p.lat, p.lng) }))
      .sort((a, b) => a.distance - b.distance);
    return {
      subway: withDist(transitData.subway, 'subway').slice(0, 5),
      bus: withDist(transitData.bus, 'bus').slice(0, 5)
    };
  }

  function renderTransitAuto(match) {
    const empty = document.getElementById('transitAutoEmpty');
    const result = document.getElementById('transitAutoResult');
    const badge = document.getElementById('transitAutoBadge');

    if (!match || (!match.subway.length && !match.bus.length)) {
      empty.style.display = '';
      result.style.display = 'none';
      badge.style.display = 'none';
      return;
    }

    empty.style.display = 'none';
    result.style.display = '';
    badge.style.display = '';

    document.getElementById('transitAutoBodySubway').innerHTML = match.subway.length
      ? `<div class="school-auto-schools">${match.subway.slice(0, 3).map(s => `<span>${s.name}(${s.line}) · ${s.distance}m</span>`).join('')}</div>`
      : `<p class="school-auto-note">반경 15km 안에 지하철역이 없어요</p>`;

    document.getElementById('transitAutoBodyBus').innerHTML = match.bus.length
      ? `<div class="school-auto-schools">${match.bus.slice(0, 3).map(s => `<span>${s.name} · ${s.distance}m</span>`).join('')}</div>`
      : `<p class="school-auto-note">주변 버스정류장 정보가 없어요</p>`;
  }

  // ---------- 포인트-인-폴리곤 (Ray casting) ----------
  function pointInRing(lng, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1];
      const xj = ring[j][0], yj = ring[j][1];
      const intersect = ((yi > lat) !== (yj > lat)) &&
        (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }
  function pointInGeometry(lng, lat, geometry) {
    if (!geometry) return false;
    if (geometry.type === 'Polygon') {
      if (!pointInRing(lng, lat, geometry.coordinates[0])) return false;
      // 이후 링(구멍)에 들어가면 폴리곤 밖으로 취급
      for (let k = 1; k < geometry.coordinates.length; k++) {
        if (pointInRing(lng, lat, geometry.coordinates[k])) return false;
      }
      return true;
    }
    if (geometry.type === 'MultiPolygon') {
      return geometry.coordinates.some(poly => pointInGeometry(lng, lat, { type: 'Polygon', coordinates: poly }));
    }
    return false;
  }

  // ---------- 주소 → 좌표가 확정되면 학군 3종 매칭 ----------
  function matchSchoolZones(lng, lat) {
    const elMatch = zoneData.elementary.find(z => pointInGeometry(lng, lat, z.geometry));
    const midMatch = zoneData.middle.find(z => pointInGeometry(lng, lat, z.geometry));
    const highMatch = zoneData.high.find(z => pointInGeometry(lng, lat, z.geometry));
    return { el: elMatch || null, mid: midMatch || null, high: highMatch || null };
  }

  function renderSchoolAuto(match) {
    const empty = document.getElementById('schoolAutoEmpty');
    const result = document.getElementById('schoolAutoResult');
    const badge = document.getElementById('schoolAutoBadge');

    if (!match || (!match.el && !match.mid && !match.high)) {
      empty.style.display = '';
      result.style.display = 'none';
      badge.style.display = 'none';
      empty.innerHTML = `
        <i class="fa-solid fa-circle-exclamation"></i>
        <p>이 주소는 학군 자동 조회 대상 지역이 아니에요.<br>(현재는 성남시 분당구만 지원돼요)</p>
      `;
      return;
    }

    empty.style.display = 'none';
    result.style.display = '';
    badge.style.display = '';

    document.getElementById('schoolAutoBodyEl').innerHTML = match.el
      ? `<div class="school-auto-schools">${match.el.schools.map(s => `<span>${s}</span>`).join('')}</div>` +
        (match.el.type === 'joint' ? `<p class="school-auto-note">공동통학구역 — 위 학교 중 하나로 배정돼요</p>` : '')
      : `<p class="school-auto-note">해당 없음</p>`;

    document.getElementById('schoolAutoBodyMid').innerHTML = match.mid
      ? `<p class="school-auto-zone">${match.mid.zone_name}</p><div class="school-auto-schools">${match.mid.schools.map(s => `<span>${s}</span>`).join('')}</div>` +
        `<p class="school-auto-note">${match.mid.schools.length}개교 중 배정돼요</p>`
      : `<p class="school-auto-note">해당 없음</p>`;

    document.getElementById('schoolAutoBodyHigh').innerHTML = match.high
      ? `<p class="school-auto-zone">${match.high.zone_name}${match.high.district_label ? ` (${match.high.district_label})` : ''}</p><div class="school-auto-schools">${match.high.schools.map(s => `<span>${s}</span>`).join('')}</div>` +
        `<p class="school-auto-note">${match.high.schools.length}개교 중 배정돼요</p>`
      : `<p class="school-auto-note">해당 없음</p>`;
  }

  // ---------- 지도 렌더링 (카카오맵) ----------
  function geoRingToPath(ring) {
    return ring.map(([lng, lat]) => new kakao.maps.LatLng(lat, lng));
  }

  function ensureMap(lng, lat) {
    const mapEl = document.getElementById('vworldMap');
    const center = new kakao.maps.LatLng(lat, lng);
    if (!kakaoMap) {
      kakaoMap = new kakao.maps.Map(mapEl, { center, level: 4 });
    } else {
      kakaoMap.setCenter(center);
    }
    if (kakaoMarker) kakaoMarker.setMap(null);
    kakaoMarker = new kakao.maps.Marker({ position: center, map: kakaoMap });

    kakaoZoneOverlays.forEach(p => p.setMap(null));
    kakaoZoneOverlays = [];
    setTimeout(() => kakaoMap.relayout(), 200);
  }

  function drawZonePolygon(zone, color) {
    if (!zone || !kakaoMap) return;
    const geom = zone.geometry;
    const polygons = geom.type === 'MultiPolygon' ? geom.coordinates : [geom.coordinates];
    polygons.forEach(rings => {
      const path = rings.map(geoRingToPath);
      const polygon = new kakao.maps.Polygon({
        map: kakaoMap,
        path,
        strokeWeight: 2,
        strokeColor: color,
        strokeOpacity: 0.9,
        fillColor: color,
        fillOpacity: 0.12
      });
      kakaoZoneOverlays.push(polygon);
    });
  }

  // ---------- 지오코딩 확정 처리 (주소 검색 선택 또는 '위치 확인' 클릭 시 공통 실행) ----------
  let currentTransitMatch = null;
  let currentLat = null;
  let currentLng = null;
  function applyGeocodedLocation(addr, lng, lat) {
    currentLat = lat;
    currentLng = lng;

    const mapPreview = document.getElementById('mapPreview');
    const mapStatusBadge = document.getElementById('mapStatusBadge');
    mapPreview.classList.add('located');
    mapStatusBadge.style.display = '';

    ensureMap(lng, lat);
    currentSchoolMatch = matchSchoolZones(lng, lat);
    if (currentSchoolMatch.el) drawZonePolygon(currentSchoolMatch.el, '#1E88FF');
    if (currentSchoolMatch.mid) drawZonePolygon(currentSchoolMatch.mid, '#17D4B3');
    if (currentSchoolMatch.high) drawZonePolygon(currentSchoolMatch.high, '#FFB020');

    renderSchoolAuto(currentSchoolMatch);

    currentTransitMatch = matchNearbyTransit(lng, lat);
    renderTransitAuto(currentTransitMatch);

    updatePreview();
  }

  // ---------- 카카오 Geocoder: 주소 검색 (자동완성 + 최종 확정 공용) ----------
  const addr1Input = document.getElementById('addr1');
  const addrSuggestList = document.getElementById('addrSuggestList');
  let addrSearchTimer = null;

  let kakaoPlaces = null; // addressSearch가 실패했을 때 쓸 키워드 검색 (더 관대하게 찾아줘요)

  function searchAddress(query) {
    return new Promise((resolve) => {
      if (!kakaoPlaces) kakaoPlaces = new kakao.maps.services.Places();

      // 키워드(장소) 검색을 먼저 시도해요. addressSearch보다 관대해서
      // "판교로25번길 8-1"처럼 건물번호까지 타이핑하는 중에도 후보를 잘 찾아줘요.
      kakaoPlaces.keywordSearch(query, (places, placesStatus) => {
        if (placesStatus === kakao.maps.services.Status.OK && places.length) {
          resolve(places.map(item => ({
            text: item.road_address_name || item.address_name || item.place_name,
            lng: Number(item.x),
            lat: Number(item.y)
          })));
          return;
        }

        // 키워드 검색이 비어있으면, 정확한 주소 매칭용 addressSearch로 한 번 더 시도해요.
        if (!kakaoGeocoder) {
          console.warn('[카카오맵] Geocoder가 아직 준비되지 않았어요.');
          resolve([]);
          return;
        }
        kakaoGeocoder.addressSearch(query, (result, status) => {
          if (status === kakao.maps.services.Status.OK) {
            resolve(result.map(item => ({
              text: (item.road_address && item.road_address.address_name) || item.address.address_name,
              lng: Number(item.x),
              lat: Number(item.y)
            })));
          } else {
            resolve([]);
          }
        });
      });
    });
  }

  function renderSuggestions(items) {
    if (!items.length) {
      addrSuggestList.innerHTML = '';
      addrSuggestList.classList.remove('show');
      return;
    }
    addrSuggestList.innerHTML = items.map((item, i) => `
      <li data-index="${i}">
        <i class="fa-solid fa-location-dot"></i>
        <span>${item.text}</span>
      </li>
    `).join('');
    addrSuggestList.classList.add('show');
    addrSuggestList.querySelectorAll('li').forEach((li, i) => {
      li.addEventListener('click', () => {
        addr1Input.value = items[i].text;
        addrSuggestList.classList.remove('show');
        applyGeocodedLocation(items[i].text, items[i].lng, items[i].lat);
      });
    });
  }

  if (addr1Input) {
    addr1Input.addEventListener('input', () => {
      clearTimeout(addrSearchTimer);
      const q = addr1Input.value.trim();
      if (q.length < 4) {
        renderSuggestions([]);
        return;
      }
      addrSearchTimer = setTimeout(async () => {
        const items = await searchAddress(q);
        renderSuggestions(items);
      }, 350);
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.field')) return;
      if (!e.target.closest('#addrSuggestList') && e.target !== addr1Input) {
        addrSuggestList.classList.remove('show');
      }
    });
  }

  // ---------- '위치 확인' 버튼 (직접 입력 후 바로 확정) ----------
  const geoCheckBtn = document.getElementById('geoCheckBtn');
  const mapPlaceholder = document.getElementById('mapPlaceholder');

  async function geocodeAddress(addr) {
    const items = await searchAddress(addr);
    return items.length ? { lng: items[0].lng, lat: items[0].lat } : null;
  }

  if (geoCheckBtn) {
    geoCheckBtn.addEventListener('click', async () => {
      const addr = addr1Input.value.trim();
      if (!addr) {
        alert('주소를 먼저 입력해주세요.');
        return;
      }
      geoCheckBtn.disabled = true;
      geoCheckBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 확인 중';
      const coord = await geocodeAddress(addr);
      geoCheckBtn.disabled = false;
      geoCheckBtn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> 위치 확인';

      if (!coord) {
        alert('입력하신 주소로 위치를 찾지 못했어요. 도로명 주소로 다시 입력해보시거나, 자동완성 목록에서 선택해주세요.');
        return;
      }
      applyGeocodedLocation(addr, coord.lng, coord.lat);
    });
  }

  // ---------- 모달: 교통정보 탭 (최소시간 / 지하철 / 버스) ----------
  let activeTransitTab = 'fastest';
  document.querySelectorAll('#transitTabs .info-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#transitTabs .info-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeTransitTab = tab.dataset.transitTab;
      updatePreview();
    });
  });

  const transitDestSearch = document.getElementById('transitDestSearch');
  if (transitDestSearch) {
    transitDestSearch.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (transitDestSearch.value.trim()) {
          alert('실제 서비스에서는 입력하신 도착지까지의 경로와 소요시간을 계산해드려요.');
        }
      }
    });
  }

  // ---------- 모달: 학군정보 탭 (초등학교 / 중학교 / 고등학교) ----------
  let activeSchoolTab = 'el';
  document.querySelectorAll('#schoolTabs .info-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#schoolTabs .info-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeSchoolTab = tab.dataset.schoolTab;
      updatePreview();
    });
  });

  // ---------- 단계 이동 ----------
  const steps = Array.from(document.querySelectorAll('.form-step'));
  const stepTabs = Array.from(document.querySelectorAll('.step-tab'));
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const submitBtn = document.getElementById('submitBtn');
  let current = 1;

  function goToStep(n) {
    current = n;
    steps.forEach(s => s.classList.toggle('active', Number(s.dataset.step) === n));
    stepTabs.forEach(t => {
      const stepNum = Number(t.dataset.step);
      t.classList.toggle('active', stepNum === n);
      t.classList.toggle('done', stepNum < n);
    });
    prevBtn.style.visibility = n === 1 ? 'hidden' : 'visible';
    nextBtn.style.display = n === steps.length ? 'none' : 'inline-block';
    submitBtn.style.display = n === steps.length ? 'inline-block' : 'none';
    window.scrollTo({ top: document.getElementById('registerForm').offsetTop - 100, behavior: 'smooth' });
  }

  nextBtn.addEventListener('click', () => { if (current < steps.length) goToStep(current + 1); });
  prevBtn.addEventListener('click', () => { if (current > 1) goToStep(current - 1); });
  stepTabs.forEach(tab => {
    tab.addEventListener('click', () => goToStep(Number(tab.dataset.step)));
  });

  // ---------- 거래유형에 따른 가격 필드 전환 ----------
  const saleFields = document.getElementById('saleFields');
  const rentFields = document.getElementById('rentFields');
  document.querySelectorAll('input[name="dealType"]').forEach(input => {
    input.addEventListener('change', () => {
      const isRent = input.value === '월세' || input.value === '전세';
      saleFields.style.display = isRent ? 'none' : 'block';
      rentFields.style.display = isRent ? 'grid' : 'none';
      if (input.value === '전세') {
        rentFields.querySelector('#monthly').closest('.field').style.display = 'none';
      } else if (isRent) {
        rentFields.querySelector('#monthly').closest('.field').style.display = 'block';
      }
      updatePreview();
    });
  });

  // ---------- 사진 업로드 & 미리보기 (최대 10장, 화살표로 넘겨보기) ----------
  const photoInput = document.getElementById('photoInput');
  const thumbGrid = document.getElementById('thumbGrid');
  const flyerPhoto = document.getElementById('flyerPhoto');
  const flyerPhotoHint = document.getElementById('flyerPhotoHint');
  const flyerPhotoPrev = document.getElementById('flyerPhotoPrev');
  const flyerPhotoNext = document.getElementById('flyerPhotoNext');
  const flyerPhotoDots = document.getElementById('flyerPhotoDots');
  const PHOTO_MAX = 10;
  let photos = [];
  let flyerPhotoIndex = 0;

  photoInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files).slice(0, PHOTO_MAX - photos.length);
    files.forEach(file => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        photos.push({ file, src: ev.target.result });
        flyerPhotoIndex = photos.length - 1; // 방금 올린 사진을 바로 보여줘요
        renderThumbs();
      };
      reader.readAsDataURL(file);
    });
  });

  function renderThumbs() {
    thumbGrid.innerHTML = '';
    photos.forEach((p, i) => {
      const div = document.createElement('div');
      div.className = 'thumb' + (i === 0 ? ' main' : '');
      div.innerHTML = `
        <img src="${p.src}" alt="매물 사진 ${i + 1}">
        ${i === 0 ? '<span class="main-tag">대표</span>' : ''}
        <button type="button" class="thumb-remove" data-index="${i}" aria-label="사진 삭제"><i class="fa-solid fa-xmark"></i></button>
      `;
      thumbGrid.appendChild(div);
    });
    thumbGrid.querySelectorAll('.thumb-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        const i = Number(btn.dataset.index);
        photos.splice(i, 1);
        if (flyerPhotoIndex >= photos.length) flyerPhotoIndex = Math.max(0, photos.length - 1);
        renderThumbs();
      });
    });
    renderFlyerPhotoCarousel();
  }

  function renderFlyerPhotoCarousel() {
    const hasPhotos = photos.length > 0;
    if (flyerPhotoIndex > photos.length - 1) flyerPhotoIndex = Math.max(0, photos.length - 1);

    flyerPhoto.style.backgroundImage = hasPhotos ? `url(${photos[flyerPhotoIndex].src})` : '';
    flyerPhoto.classList.toggle('has-photo', hasPhotos);
    flyerPhotoHint.style.display = hasPhotos ? 'none' : '';

    const showNav = photos.length > 1;
    flyerPhotoPrev.style.display = showNav ? '' : 'none';
    flyerPhotoNext.style.display = showNav ? '' : 'none';
    flyerPhotoDots.innerHTML = showNav
      ? photos.map((_, i) => `<span class="${i === flyerPhotoIndex ? 'active' : ''}"></span>`).join('')
      : '';
  }

  flyerPhotoPrev.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!photos.length) return;
    flyerPhotoIndex = (flyerPhotoIndex - 1 + photos.length) % photos.length;
    renderFlyerPhotoCarousel();
  });
  flyerPhotoNext.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!photos.length) return;
    flyerPhotoIndex = (flyerPhotoIndex + 1) % photos.length;
    renderFlyerPhotoCarousel();
  });

  // ---------- 히어로 예시 카드 사진 캐러셀 (register_ex_1.png ~ register_ex_10.png) ----------
  function preloadImage(path) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(path);
      img.onerror = () => resolve(null);
      img.src = path;
    });
  }

  async function initFyPhotoCarousel() {
    const numberedCandidates = [];
    for (let i = 1; i <= 10; i++) numberedCandidates.push(`../../static/images/register_ex_${i}.png`);

    const numberedResults = await Promise.all(numberedCandidates.map(preloadImage));
    let slides = numberedResults.filter(Boolean);

    if (!slides.length) {
      // 번호 붙은 파일이 없으면, 기존 단일 파일(register_ex.png)로 대신해요.
      const fallback = await preloadImage('../../static/images/register_ex.png');
      if (fallback) slides = [fallback];
    }
    if (!slides.length) return; // 예시 사진이 하나도 없으면 빈 배경으로 둬요.

    let idx = 0;
    const fyPhoto = document.getElementById('fyPhoto');
    const dotsEl = document.getElementById('fyPhotoDots');
    const prevBtn = document.getElementById('fyPhotoPrev');
    const nextBtn = document.getElementById('fyPhotoNext');

    function render() {
      fyPhoto.style.backgroundImage = `url("${slides[idx]}")`;
      dotsEl.innerHTML = slides.length > 1
        ? slides.map((_, i) => `<span class="${i === idx ? 'active' : ''}"></span>`).join('')
        : '';
    }
    if (slides.length <= 1) {
      prevBtn.style.display = 'none';
      nextBtn.style.display = 'none';
    } else {
      prevBtn.addEventListener('click', () => { idx = (idx - 1 + slides.length) % slides.length; render(); });
      nextBtn.addEventListener('click', () => { idx = (idx + 1) % slides.length; render(); });
    }
    render();
  }
  initFyPhotoCarousel();

  // ---------- 억/만원 단위 변환 (가독성용) ----------
  function formatKoreanPrice(manwon) {
    const num = Number(manwon);
    if (!num || isNaN(num)) return '';
    const eok = Math.floor(num / 10000);
    const rest = num % 10000;
    if (eok > 0 && rest > 0) return `${eok}억 ${rest.toLocaleString('ko-KR')}만원`;
    if (eok > 0) return `${eok}억원`;
    return `${num.toLocaleString('ko-KR')}만원`;
  }

  // ---------- 가격 입력 콤마 포맷 + 억/만원 실시간 변환 힌트 ----------
  const priceHintMap = { price: 'priceHint', deposit: 'depositHint', monthly: 'monthlyHint' };
  ['price', 'deposit', 'monthly'].forEach(id => {
    const el = document.getElementById(id);
    const hintEl = document.getElementById(priceHintMap[id]);
    el.addEventListener('input', () => {
      const digits = el.value.replace(/[^0-9]/g, '');
      el.value = digits ? Number(digits).toLocaleString('ko-KR') : '';
      if (hintEl) hintEl.textContent = digits ? `= ${formatKoreanPrice(digits)}` : '';
      updatePreview();
    });
  });

  // ---------- 실시간 미리보기(전단지) 업데이트 ----------
  const flyerDeal = document.getElementById('flyerDeal');
  const flyerPrice = document.getElementById('flyerPrice');
  const flyerAddr = document.getElementById('flyerAddr');
  const flyerSpec = document.getElementById('flyerSpec');
  const flyerTags = document.getElementById('flyerTags');
  const flyerOptions = document.getElementById('flyerOptions');
  const flyerFee = document.getElementById('flyerFee');
  const flyerTransit = document.getElementById('flyerTransit');
  const flyerSchool = document.getElementById('flyerSchool');
  const modalDeal = document.getElementById('modalDeal');
  const modalPrice = document.getElementById('modalPrice');
  const modalAddr = document.getElementById('modalAddr');
  const modalSpec = document.getElementById('modalSpec');

  function currentDealType() {
    const checked = document.querySelector('input[name="dealType"]:checked');
    return checked ? checked.value : '매매';
  }

  function updatePreview() {
    const deal = currentDealType();
    flyerDeal.textContent = deal;

    if (deal === '매매') {
      const price = document.getElementById('price').value;
      flyerPrice.textContent = price ? formatKoreanPrice(price.replace(/[^0-9]/g, '')) : '가격 미입력';
    } else if (deal === '전세') {
      const deposit = document.getElementById('deposit').value;
      flyerPrice.textContent = deposit ? `전세 ${formatKoreanPrice(deposit.replace(/[^0-9]/g, ''))}` : '보증금 미입력';
    } else {
      const deposit = document.getElementById('deposit').value;
      const monthly = document.getElementById('monthly').value;
      flyerPrice.textContent = (deposit || monthly)
        ? `${formatKoreanPrice(deposit.replace(/[^0-9]/g, '')) || '0만원'} / ${formatKoreanPrice(monthly.replace(/[^0-9]/g, '')) || '0만원'}`
        : '보증금/월세 미입력';
    }

    const addr1 = document.getElementById('addr1').value;
    const addr2 = document.getElementById('addr2').value;
    flyerAddr.textContent = addr1 ? `${addr1}${addr2 ? ' · ' + addr2 : ''}` : '주소를 입력해주세요';

    const area = document.getElementById('area').value;
    const rooms = document.getElementById('rooms').value;
    const baths = document.getElementById('baths').value;
    const floor = document.getElementById('floor').value;
    const specParts = [];
    if (area) specParts.push(`${area}㎡`);
    if (rooms) specParts.push(`방${rooms}`);
    if (baths) specParts.push(`욕${baths}`);
    if (floor) specParts.push(`${floor}층`);
    flyerSpec.textContent = specParts.length ? specParts.join(' · ') : '면적 · 방 · 욕실 · 층수';

    const tags = Array.from(document.querySelectorAll('#tagGrid input:checked')).map(i => i.value);
    flyerTags.innerHTML = tags.length ? tags.map(t => `<span>${t}</span>`).join('') : '<span class="empty-hint">아직 입력된 특징이 없어요</span>';

    const options = Array.from(document.querySelectorAll('#optionGrid input:checked')).map(i => i.value);
    flyerOptions.innerHTML = options.length ? options.map(o => `<span>${o}</span>`).join('') : '<span class="empty-hint">아직 입력된 옵션이 없어요</span>';

    // 관리비 정보
    const feeParts = [];
    const fee = document.getElementById('maintenanceFee').value;
    if (fee) feeParts.push(`일반(공용) 관리비 ${fee}만원`);
    const ALL_UTILITIES = ['전기', '수도', '가스', '인터넷', 'TV'];
    const utilities = Array.from(document.querySelectorAll('#utilityGroup input:checked')).map(i => i.value);
    const notIncluded = ALL_UTILITIES.filter(u => !utilities.includes(u));
    const etcFee = document.getElementById('etcFee').value;
    const hasFeeInfo = Boolean(fee || etcFee || utilities.length);
    if (utilities.length) feeParts.push(`포함: ${utilities.join(', ')}`);
    if (hasFeeInfo && notIncluded.length) feeParts.push(`포함되지 않음: ${notIncluded.join(', ')}`);
    if (etcFee) feeParts.push(etcFee);
    flyerFee.innerHTML = feeParts.length
      ? feeParts.map(m => `<div>${m}</div>`).join('')
      : '<div class="empty-hint">관리비 정보를 입력하면 여기에 표시돼요</div>';

    // 교통정보 (탭에 따라 다르게 표시 — 주소 기준 직선거리 자동 계산)
    if (!currentTransitMatch) {
      flyerTransit.innerHTML = '<div class="empty-hint">1단계에서 주소를 입력하고 위치를 확인하면 자동으로 표시돼요</div>';
    } else if (activeTransitTab === 'bus') {
      flyerTransit.innerHTML = currentTransitMatch.bus.length
        ? currentTransitMatch.bus.map(s => `
            <div class="transit-result-row">
              <i class="fa-solid fa-bus"></i>
              <span class="transit-station-name">${s.name}</span>
              <span class="transit-walk-time">${s.distance}m</span>
            </div>
          `).join('')
        : '<div class="empty-hint">주변 버스정류장 정보가 없어요</div>';
    } else if (activeTransitTab === 'subway') {
      flyerTransit.innerHTML = currentTransitMatch.subway.length
        ? currentTransitMatch.subway.map(s => `
            <div class="transit-result-row">
              <i class="fa-solid fa-train-subway"></i>
              <span class="transit-station-name">${s.name} (${s.line})</span>
              <span class="transit-walk-time">${s.distance}m</span>
            </div>
          `).join('')
        : '<div class="empty-hint">반경 15km 안에 지하철역이 없어요</div>';
    } else {
      // 최소시간 탭: 지하철·버스 통합해서 거리 가까운 순으로
      const combined = [...currentTransitMatch.subway, ...currentTransitMatch.bus]
        .sort((a, b) => a.distance - b.distance)
        .slice(0, 5);
      flyerTransit.innerHTML = combined.length
        ? combined.map(s => `
            <div class="transit-result-row">
              <i class="fa-solid ${s.type === 'subway' ? 'fa-train-subway' : 'fa-bus'}"></i>
              <span class="transit-station-name">${s.name}${s.line ? ` (${s.line})` : ''}</span>
              <span class="transit-walk-time">${s.distance}m</span>
            </div>
          `).join('')
        : '<div class="empty-hint">주변 교통정보가 없어요</div>';
    }

    // 학군정보 (탭으로 선택한 학교급만 표시 — 주소 기반 자동 매칭 결과)
    const schoolLabels = { el: '초등학교', mid: '중학교', high: '고등학교' };
    const activeLabel = schoolLabels[activeSchoolTab];
    const zoneMatch = currentSchoolMatch ? currentSchoolMatch[activeSchoolTab] : null;

    if (!currentSchoolMatch) {
      flyerSchool.innerHTML = `<div class="empty-hint">1단계에서 주소를 입력하고 위치를 확인하면 ${activeLabel} 학군이 자동으로 표시돼요</div>`;
    } else if (!zoneMatch) {
      flyerSchool.innerHTML = `<div class="empty-hint">이 주소는 ${activeLabel} 학군 자동 조회 대상 지역이 아니에요 (분당구만 지원)</div>`;
    } else {
      const zoneLabel = zoneMatch.zone_name
        ? `${zoneMatch.zone_name}${zoneMatch.district_label ? ` (${zoneMatch.district_label})` : ''}`
        : (zoneMatch.type === 'joint' ? '공동통학구역 (택1 배정)' : activeLabel + ' 통학구역');
      flyerSchool.innerHTML = `
        <div class="school-row">
          <span class="school-level-tag">${zoneLabel}</span>
        </div>
      ` + zoneMatch.schools.map(name => `
          <div class="school-row">
            <span class="school-name">${name}</span>
            <i class="fa-solid fa-location-dot school-map-icon" title="지도 연동됨"></i>
          </div>
        `).join('');
    }

    // 카드 요약과 동일한 내용을 상세정보 모달에도 반영해요.
    modalDeal.textContent = flyerDeal.textContent;
    modalPrice.textContent = flyerPrice.textContent;
    modalAddr.textContent = flyerAddr.textContent;
    modalSpec.textContent = flyerSpec.textContent;
  }

  document.querySelectorAll('#registerForm input, #registerForm select').forEach(el => {
    el.addEventListener('input', updatePreview);
    el.addEventListener('change', updatePreview);
  });

  // ---------- 제출 ----------
  document.getElementById('listingForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (current < steps.length) {
      alert('아직 입력하지 않은 정보가 있어요. 마지막 단계까지 입력을 완료해주세요.');
      return;
    }
    if (!document.getElementById('ownerCheck').checked) {
      alert('소유자 확인 동의가 필요해요.');
      return;
    }
    if (currentLat == null || currentLng == null) {
      alert('주소를 검색해서 위치를 확인해주세요.');
      return;
    }

    function getCheckedValues(containerId) {
      return Array.from(document.querySelectorAll(`#${containerId} input[type="checkbox"]:checked`))
        .map(el => el.value);
    }

    const dealType = document.querySelector('input[name="dealType"]:checked')?.value || '';
    const priceVal = parseInt(document.getElementById('price').value, 10);
    const depositVal = parseInt(document.getElementById('deposit').value, 10);
    const monthlyVal = parseInt(document.getElementById('monthly').value, 10);

    const payload = {
      propertyType: document.querySelector('input[name="propertyType"]:checked')?.value || '',
      dealType,
      address1: document.getElementById('addr1').value,
      address2: document.getElementById('addr2').value,
      latitude: currentLat,
      longitude: currentLng,
      area: parseFloat(document.getElementById('area').value) || null,
      floorInfo: document.getElementById('floor').value,
      rooms: parseInt(document.getElementById('rooms').value, 10) || null,
      baths: parseInt(document.getElementById('baths').value, 10) || null,
      maintenanceFee: parseInt(document.getElementById('maintenanceFee').value, 10) || null,
      etcFee: document.getElementById('etcFee').value,
      tags: getCheckedValues('tagGrid'),
      options: getCheckedValues('optionGrid'),
      utilities: getCheckedValues('utilityGroup'),
      transitInfo: currentTransitMatch ? JSON.stringify({
        subway: currentTransitMatch.subway[0] ? currentTransitMatch.subway[0].name : null,
        bus: currentTransitMatch.bus.slice(0, 3).map(b => b.name)
      }) : null,
      schoolInfo: currentSchoolMatch ? JSON.stringify({
        elementary: currentSchoolMatch.el ? currentSchoolMatch.el.schools[0] : null,
        middle: currentSchoolMatch.mid ? currentSchoolMatch.mid.schools[0] : null
      }) : null,
      price: dealType === '매매' ? (Number.isFinite(priceVal) ? priceVal : null) : null,
      deposit: (dealType === '전세' || dealType === '월세') ? (Number.isFinite(depositVal) ? depositVal : null) : null,
      monthly: dealType === '월세' ? (Number.isFinite(monthlyVal) ? monthlyVal : null) : null,
      ownerName: document.getElementById('ownerName').value,
      ownerPhone: document.getElementById('ownerPhone').value
    };

    submitBtn.disabled = true;
    const originalBtnText = submitBtn.textContent;
    submitBtn.textContent = '등록 중...';

    try {
      const res = await fetch('/api/properties', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (!data.success) {
        alert(data.message || '매물 등록에 실패했어요.');
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
        return;
      }

      const propertyId = data.propertyId;

      // 첨부한 서류가 있으면 순서대로 업로드 (실패해도 등록 자체는 이미 완료된 상태라 계속 진행)
      const docInputs = [
        { id: 'ownershipDoc', type: 'OWNERSHIP' },
        { id: 'buildingRegisterDoc', type: 'BUILDING_REGISTER' },
        { id: 'landRegisterDoc', type: 'LAND_REGISTER' },
        { id: 'sealCertificateDoc', type: 'SEAL_CERTIFICATE' }
      ];

      for (const doc of docInputs) {
        const input = document.getElementById(doc.id);
        if (input && input.files && input.files[0]) {
          const formData = new FormData();
          formData.append('docType', doc.type);
          formData.append('file', input.files[0]);
          try {
            await fetch(`/api/properties/${propertyId}/documents`, { method: 'POST', body: formData });
          } catch (err) {
            console.error('서류 업로드 실패:', doc.type, err);
          }
        }
      }

      // 사진 업로드 (STEP3에서 선택한 것들, 0번이 대표 사진)
      for (let i = 0; i < photos.length; i++) {
        const formData = new FormData();
        formData.append('file', photos[i].file);
        formData.append('sortOrder', String(i));
        try {
          await fetch(`/api/properties/${propertyId}/photos`, { method: 'POST', body: formData });
        } catch (err) {
          console.error('사진 업로드 실패:', i, err);
        }
      }

      let message = '매물 등록 신청이 접수됐어요. 담당자 확인 후 24시간 이내 게시돼요.';
      if (data.nameMismatch) {
        message += '\n\n' + data.nameMismatchMessage;
      }
      alert(message);
      window.location.href = '/';
    } catch (err) {
      alert('서버에 연결할 수 없어요. 잠시 후 다시 시도해주세요.');
      submitBtn.disabled = false;
      submitBtn.textContent = originalBtnText;
    }
  });

  updatePreview();

  // ---------- 상세정보 모달 ----------
  const flyerCard = document.getElementById('flyerCard');
  const detailModal = document.getElementById('detailModal');
  const detailModalBackdrop = document.getElementById('detailModalBackdrop');
  const detailModalClose = document.getElementById('detailModalClose');

  function openDetailModal() {
    detailModal.classList.add('open');
    detailModal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  function closeDetailModal() {
    detailModal.classList.remove('open');
    detailModal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  if (flyerCard) {
    flyerCard.addEventListener('click', openDetailModal);
    flyerCard.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openDetailModal();
      }
    });
  }
  if (detailModalClose) detailModalClose.addEventListener('click', closeDetailModal);
  if (detailModalBackdrop) detailModalBackdrop.addEventListener('click', closeDetailModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && detailModal.classList.contains('open')) closeDetailModal();
  });

  // ---------- Back to Top FAB ----------
  const backToTop = document.getElementById('backToTop');
  if (backToTop) {
    window.addEventListener('scroll', () => {
      backToTop.classList.toggle('show', window.scrollY > 400);
    });
    backToTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

/* ----------------------------------------------------------
   서류 선택 시 파일명 표시 (기존 대형 스크립트와 독립적으로 동작)
   ---------------------------------------------------------- */
  document.querySelectorAll('input[type="file"][data-doc-type]').forEach((input) => {
    input.addEventListener('change', (e) => {
      const hint = document.querySelector(`[data-doc-hint="${input.id}"]`);
      if (!hint) return;
      const file = e.target.files[0];
      hint.textContent = file ? `선택됨: ${file.name}` : '선택한 파일이 없어요.';
    });
  });
