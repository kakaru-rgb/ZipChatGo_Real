/* 대화 시작 문장 빠른 입력 */
document.querySelectorAll(".quick-tags button").forEach(tag => {
  tag.addEventListener("click", () => {
    const input = document.querySelector(".ai-search-box input");
    if (input) {
      input.value = tag.innerText;
      input.focus();
    }
  });
});

// 참고: 예전에는 여기서 로그인 여부를 localStorage로 체크해서
// 로그인 필요한 카드(feature-link) 클릭 시 강제로 로그인 페이지로 보냈지만,
// 지금은 서버 쪽 AuthInterceptor가 보호된 경로 접근을 알아서 처리하므로
// 이 파일에서 별도로 막을 필요가 없어졌어요. index.html의 th:href 기본 이동을 그대로 따릅니다.

// AI 대화 시작 버튼은 아직 실제 채팅 페이지가 없어서, 이번엔 클릭해도 아무 동작 안 하도록 비워둡니다.
// (페이지가 준비되면 여기에 이동 로직을 추가하면 됩니다.)
