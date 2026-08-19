(function () {
  const core = document.createElement("script");
  core.src = "/static/js/app-core.js";
  core.onload = function () {
    try {
      const routePatches = {
        "baegot-life-loop": {
          name: "배곧생명공원 수변 둘레길",
          routeType: "순환형",
          distance: 2.3,
          duration: 21,
          difficulty: "쉬움",
          surface: "수변·공원 산책로",
          highlights: ["수변 둘레길", "평탄한 구간", "순환형"],
          basis: "OpenStreetMap 보행망과 배곧생명공원 내부 산책로를 기준으로 구성한 수변 순환 코스 · 실제 통행 가능 여부는 현장에서 확인"
        },
        "okgu-park-loop": {
          name: "옥구공원 공원 둘레길",
          routeType: "순환형",
          distance: 2.2,
          duration: 20,
          difficulty: "보통",
          surface: "공원 산책로·완만한 언덕",
          highlights: ["공원 둘레길", "완만한 업다운", "순환형"],
          basis: "OpenStreetMap 보행망과 옥구공원 내부 산책로를 기준으로 구성한 공원 순환 코스 · 급경사 정상부보다 하부 공원길 중심"
        },
        "oido-history-coast": {
          name: "오이도 해안 산책로 코스",
          routeType: "해안 연결형",
          distance: 5.3,
          duration: 48,
          difficulty: "보통",
          surface: "해안 보행로·일부 생활도로",
          highlights: ["오이도 해안", "노을 구간", "해안 연결형"],
          basis: "OpenStreetMap 보행망을 따라 오이도 해안 보행축과 선사유적공원 방향을 연결한 코스 · 생활도로와 횡단 구간이 일부 포함"
        },
        "sincheon-park-link": {
          name: "신천 도심공원 순환 코스",
          routeType: "순환형",
          distance: 2.2,
          duration: 20,
          difficulty: "보통",
          surface: "도심 보행로·공원길",
          highlights: ["도심 접근성", "공원 연결", "순환형"],
          basis: "OpenStreetMap 보행망을 따라 신천 생활권 공원과 보행로를 연결한 짧은 순환 코스 · 교차로와 생활도로 구간 주의"
        },
        "eungye-lake-loop": {
          name: "은계호수공원 수변 왕복 코스",
          routeType: "왕복형",
          distance: 1.7,
          duration: 16,
          difficulty: "쉬움",
          surface: "호수 남·서측 수변 보행로",
          highlights: ["호수 조망", "평탄한 수변길", "왕복형"],
          basis: "OpenStreetMap 보행 라우팅망으로 확인되는 은계호수공원 남·서측 수변 보행로를 왕복하도록 구성 · 실제 라우팅 거리 약 1.70km"
        },
        "daeya-eungye-forest": {
          name: "대야·은계숲 녹지 순환 코스",
          routeType: "녹지 연결형",
          distance: 3.6,
          duration: 33,
          difficulty: "보통",
          surface: "공원길·녹지축·생활 보행로",
          highlights: ["대야공원", "은계권 녹지", "녹지 연결형"],
          basis: "OpenStreetMap 보행망을 따라 대야공원과 은계권 녹지축을 연결한 코스 · 생활도로와 횡단보도 구간이 일부 포함"
        }
      };

      RUNNING_ROUTES.forEach(function (route) {
        const patch = routePatches[route.id];
        if (patch) Object.assign(route, patch);
      });

      if (SERVICE_GUIDES && SERVICE_GUIDES.running) {
        SERVICE_GUIDES.running.summary = "공원·호수·해안의 실제 보행 가능한 경로를 기준으로 구성한 6개 러닝코스를 비교합니다.";
        SERVICE_GUIDES.running.steps[0].body = "러닝코스 메뉴에서 거리, 예상 시간, 난이도, 노면과 코스 형태를 비교해 보세요. 공원 둘레길·수변길·해안길처럼 코스 성격이 바로 보이도록 정리했습니다.";
        SERVICE_GUIDES.running.steps[1].body = "코스 카드를 누르면 네이버 지도에 실제 좌표 기반 경로가 표시됩니다. 선이 공원·호수·해안의 보행 가능한 경로를 따라가는지 확인하고, 출발 전 공사·통제·야간 조명 상태를 한 번 더 확인해 주세요.";
        SERVICE_GUIDES.running.steps[1].note = "지도 경로는 OpenStreetMap 보행망과 공원·수변 보행로를 기준으로 구성한 추천 동선입니다. 현장 상황에 따라 일부 구간 이용이 제한될 수 있습니다.";
      }

      const runningPageCopy = document.querySelector("#page-running .page-heading p");
      if (runningPageCopy) runningPageCopy.textContent = "공원·호수·해안의 보행 가능한 경로를 기준으로 구성한 6개 코스를 확인해 보세요.";
      const runningHeadCopy = document.querySelector("#page-running .running-head p");
      if (runningHeadCopy) runningHeadCopy.textContent = "직선으로 지점을 잇지 않고 실제 보행망과 공원·수변 산책로를 따라 구성했습니다. 출발 전 현장 통제 여부를 확인해 주세요.";
      const routeMapNote = document.querySelector(".route-map-note");
      if (routeMapNote) routeMapNote.textContent = "공원·수변·해안의 보행 가능한 경로를 따라 추천 동선을 표시합니다.";

      renderRoutes = function () {
        $("running-list").innerHTML = RUNNING_ROUTES.map(function (route) {
          return `<button class="running-card" data-route="${route.id}" type="button"><span>${areaById(route.area)?.name || "시흥"} · ${route.difficulty}</span><h3>${route.name}</h3><p>${route.surface}</p><div><b>${route.distance}km</b><b>${route.duration}분</b></div><small>${route.routeType || "추천 코스"} · 상세 경로 보기 →</small></button>`;
        }).join("");
        document.querySelectorAll("[data-route]").forEach(function (button) {
          button.addEventListener("click", function () {
            const route = RUNNING_ROUTES.find(function (item) { return item.id === button.dataset.route; });
            openAnimatedRouteDialog(route);
          });
        });
      };

      if (document.getElementById("running-list")) renderRoutes();
    } catch (error) {
      console.error("러닝코스 고도화 적용 실패", error);
    }
  };
  core.onerror = function () {
    console.error("기존 앱 코드를 불러오지 못했습니다.");
  };
  document.head.appendChild(core);
})();
