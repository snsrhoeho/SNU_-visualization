(function () {
  const core = document.createElement("script");
  core.src = "/static/js/app-core.js";
  core.onload = function () {
    try {
      const routePatches = {
        "baegot-life-loop": {
          name: "배곧생명공원 수변 둘레길",
          routeType: "순환형",
          distance: 1.4,
          duration: 13,
          difficulty: "쉬움",
          surface: "공원 외곽·수변 산책로",
          highlights: ["공원 외곽 순환", "수변 산책로", "평탄한 구간"],
          basis: "OpenStreetMap 보행 경로 70/70개 좌표 매칭 · 공원 외곽과 수변 보행로를 따라 한 바퀴 순환 · 짧은 계단 구간 포함"
        },
        "okgu-park-loop": {
          name: "옥구공원 공원 둘레길",
          routeType: "순환형",
          distance: 1.2,
          duration: 11,
          difficulty: "보통",
          surface: "공원 하부 산책로·완만한 경사",
          highlights: ["공원 하부 순환", "정상 오르막 제외", "한국정원 인근"],
          basis: "OpenStreetMap 보행 경로 61/61개 좌표 매칭 · 옥구산 정상 방향을 제외하고 공원 하부 산책로 중심으로 순환"
        },
        "oido-history-coast": {
          name: "오이도 해안 산책로 코스",
          routeType: "왕복형",
          distance: 2.1,
          duration: 19,
          difficulty: "쉬움",
          surface: "해안 산책로 왕복",
          highlights: ["해안선 왕복", "서해 조망", "노을 구간"],
          basis: "OpenStreetMap 해안 보행 경로 좌표를 따라 왕복 · 내륙 블록과 수면 횡단 제거",
          coordinates: [[126.688799,37.342312],[126.690284,37.341957],[126.689915,37.340942],[126.690026,37.340916],[126.689821,37.340437],[126.690884,37.340186],[126.691281,37.339972],[126.691772,37.339541],[126.691996,37.339206],[126.692104,37.338951],[126.692161,37.338593],[126.692164,37.337839],[126.692045,37.337041],[126.691669,37.335887],[126.691584,37.335497],[126.690864,37.335354],[126.691584,37.335497],[126.691669,37.335887],[126.692045,37.337041],[126.692164,37.337839],[126.692161,37.338593],[126.692104,37.338951],[126.691996,37.339206],[126.691772,37.339541],[126.691281,37.339972],[126.690884,37.340186],[126.689821,37.340437],[126.690026,37.340916],[126.689915,37.340942],[126.690284,37.341957],[126.688799,37.342312]]
        },
        "sincheon-park-link": {
          name: "신천근린공원 둘레길",
          routeType: "순환형",
          distance: 0.6,
          duration: 6,
          difficulty: "쉬움",
          surface: "근린공원 외곽 산책로",
          highlights: ["공원 외곽 1바퀴", "도심 블록 연결 제외", "반복 주행 가능"],
          basis: "OpenStreetMap 신천공원 외곽 형상에 맞춘 순환 동선 · 도심 여러 블록을 잇던 기존 구간 제거",
          coordinates: [[126.7856031,37.4369418],[126.7859976,37.4351708],[126.7859294,37.4350744],[126.7858231,37.4349901],[126.7857473,37.4349358],[126.7855956,37.4349178],[126.7855121,37.4349178],[126.7853604,37.4349298],[126.7851935,37.4349479],[126.7849962,37.434984],[126.7847231,37.4350262],[126.7844955,37.4350864],[126.784359,37.4351226],[126.7842224,37.4351828],[126.7840859,37.435237],[126.7839948,37.4352611],[126.7841693,37.4353093],[126.7843134,37.435472],[126.7843893,37.4359418],[126.7851176,37.4366587],[126.7852162,37.436743],[126.7855424,37.4369177],[126.7856031,37.4369418]]
        },
        "eungye-lake-loop": {
          name: "은계호수공원 호수 둘레길",
          routeType: "순환형",
          distance: 1.3,
          duration: 12,
          difficulty: "쉬움",
          surface: "호수 외곽 수변 산책로",
          highlights: ["호수 외곽 1바퀴", "수변 조망", "평탄한 순환"],
          basis: "OpenStreetMap 은계호수 외곽 형상에서 물 경계 바깥쪽으로 보정한 수변 순환 시연 동선 · 출발 전 현장 보행로 확인 필요",
          coordinates: [[126.8042882,37.4474774],[126.805528,37.447842],[126.8061708,37.447204],[126.806676,37.4469853],[126.8073877,37.4462926],[126.8082602,37.4453265],[126.808375,37.4452536],[126.8076403,37.4437042],[126.8076174,37.4435401],[126.8073647,37.4435948],[126.8073366,37.4436079],[126.8058265,37.4443057],[126.805571,37.4444342],[126.8053128,37.4446638],[126.8051376,37.4448708],[126.8049852,37.4451261],[126.8046503,37.4453848],[126.8044447,37.4457596],[126.8045178,37.4462379],[126.8049999,37.4464749],[126.8042882,37.4474774]]
        },
        "daeya-eungye-forest": {
          name: "대야·은계숲 녹지 코스",
          routeType: "녹지 연결형",
          distance: 2.4,
          duration: 22,
          difficulty: "보통",
          surface: "녹지 보행로·일부 생활도로",
          highlights: ["은계숲 생태공원", "밤비천 녹지축", "생활도로 최소화"],
          basis: "OpenStreetMap 보행 경로 74/74개 좌표 매칭 · 은계숲 생태공원과 밤비천 녹지축 중심 · 공원 연결에 필요한 일부 생활도로 포함"
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
