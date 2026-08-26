const mapRecenter = document.getElementById('mapRecenter');
const propertyInfo = document.getElementById('propertyInfo');
const propertyVideoModal = document.getElementById('propertyVideoModal');
const propertyYoutube = document.getElementById('propertyYoutube');
const propertyVideoTitle = document.getElementById('propertyVideoTitle');
const propertyVideoClose = document.getElementById('propertyVideoClose');
const propertyVideoBackdrop = document.getElementById('propertyVideoBackdrop');

let activeHome = 0;

const liveMap = new naver.maps.Map('liveMap', {
  center: new naver.maps.LatLng(37.5446, 127.0556),
  zoom: 15,
  zoomControl: true,
  zoomControlOptions: {
    position: naver.maps.Position.RIGHT_BOTTOM,
    style: naver.maps.ZoomControlStyle.SMALL
  },
  draggable: true,
  scrollWheel: true,
  disableDoubleClickZoom: false
});

const fallbackHomes = [
  { name: '성수 리버뷰 84㎡', price: '매매 12.8억', lat: 37.5446, lng: 127.0556, pick: true, youtubeId: '2NpswwcViDE' },
  { name: '서울숲 시티뷰 59㎡', price: '전세 7.2억', lat: 37.5483, lng: 127.0447, youtubeId: 'nD4g9J7o-Yc' },
  { name: '왕십리 파크뷰 74㎡', price: '매매 10.4억', lat: 37.5385, lng: 127.0584, youtubeId: 'skvgwoCisMU' }
];

let recommendedHomes = fallbackHomes;
let markers = [];

function focusHome(home, index) {
  activeHome = index;
  propertyInfo.textContent = `AI 추천 매물 · ${home.name} · ${home.price}`;
  liveMap.panTo(new naver.maps.LatLng(home.lat, home.lng));
  liveMap.setZoom(home.pick ? 16 : 15.5);
}

function openPropertyVideo(home) {
  propertyVideoTitle.textContent = `${home.name} 영상`;
  propertyYoutube.src = `https://www.youtube.com/embed/${home.youtubeId}?autoplay=1&rel=0`;
  propertyVideoModal.hidden = false;
  propertyVideoModal.setAttribute('aria-hidden', 'false');
  propertyVideoClose.focus();
}

function closePropertyVideo() {
  propertyYoutube.src = '';
  propertyVideoModal.hidden = true;
  propertyVideoModal.setAttribute('aria-hidden', 'true');
}

function renderHomeMarkers() {
  markers.forEach(marker => marker.setMap(null));
  markers = recommendedHomes.map((home, index) => {
    const marker = new naver.maps.Marker({
      position: new naver.maps.LatLng(home.lat, home.lng),
      map: liveMap,
      title: `${home.name} - ${home.price}`
    });

    naver.maps.Event.addListener(marker, 'click', () => {
      focusHome(home, index);
      openPropertyVideo(home);
    });
    return marker;
  });
}

async function loadRecommendedHomes() {
  try {
    const response = await fetch('/api/live/recommendations');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const homes = await response.json();
    if (!Array.isArray(homes) || homes.length === 0) throw new Error('추천 매물이 없습니다.');
    recommendedHomes = homes;
  } catch (error) {
    console.warn('추천 매물 API를 사용할 수 없어 데모 데이터를 사용합니다.', error);
  }

  renderHomeMarkers();
  focusHome(recommendedHomes[0], 0);
}

mapRecenter?.addEventListener('click', () => focusHome(recommendedHomes[activeHome], activeHome));
propertyVideoClose?.addEventListener('click', closePropertyVideo);
propertyVideoBackdrop?.addEventListener('click', closePropertyVideo);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !propertyVideoModal.hidden) closePropertyVideo();
});

loadRecommendedHomes();
setInterval(() => {
  const next = (activeHome + 1) % recommendedHomes.length;
  focusHome(recommendedHomes[next], next);
}, 9000);
