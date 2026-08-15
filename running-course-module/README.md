# 러닝코스 독립 모듈

러닝코스 카드, 상세 팝업, 코스 선 그리기, 러너 애니메이션만 분리한 파일입니다. 다른 페이지의 추천·지도·데이터 코드에 의존하지 않습니다.

## 필요한 파일

- `running-course.js`: 코스 데이터와 UI·애니메이션 동작
- `running-course.css`: 카드와 팝업 디자인
- `example.html`: 단독 실행 및 합치기 예시

## 기존 사이트에 합치는 방법

1. `running-course.js`, `running-course.css`를 대상 프로젝트로 복사합니다.
2. 페이지에 다음 요소를 추가합니다.

```html
<link rel="stylesheet" href="./running-course.css" />
<div id="running-course-app"></div>
<script src="./running-course.js"></script>
<script>
  RunningCourse.init({ mount: "#running-course-app" });
</script>
```

모듈이 카드와 팝업을 자동으로 만듭니다. 카드를 누르면 러너가 코스를 따라 한 번만 움직이고, `움직임 다시 보기`를 누르면 다시 실행됩니다.

## 코스 데이터 교체

`RunningCourse.init({ routes: [...] })`로 같은 필드 구조의 배열을 전달하거나 `running-course.js`의 `DEFAULT_ROUTES`를 수정합니다. `points`는 실제 지도 좌표가 아니라 팝업 SVG 안에서 사용할 `[x, y]` 좌표 목록입니다.

```js
{
  id: "my-route",
  area: "배곧동",
  name: "코스 이름",
  distance: 3.2,
  duration: 28,
  difficulty: "쉬움",
  surface: "공원 산책로",
  summary: "코스 설명",
  highlights: ["수변 풍경", "평탄한 구간"],
  basis: "동선 산정 기준",
  points: [[14, 69], [22, 60], [27, 66], [14, 69]]
}
```

이 모듈은 API 키가 필요 없습니다. 향후 실제 지도 API 위에서 움직이게 할 때는 `points` 대신 지도 좌표를 투영하는 부분만 교체하면 됩니다.
