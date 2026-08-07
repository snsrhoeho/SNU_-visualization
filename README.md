# 시흥생활핏

시흥시 1인 가구가 중요하게 생각하는 생활 인프라를 고르면, 6개 행정동의 조건 충족 여부를 비교하고 적합한 동네를 추천하는 데이터 시각화 웹 서비스입니다.

## 구현된 기능

- 음식점, 카페, 코인세탁방, 편의점, 마트, 지하철역, 버스정류장, 공원·러닝, 병원, 약국 다중 선택
- 도보 5분(약 330m), 10분(약 670m), 15분(약 1km) 범위 선택
- 가중치 없이 `충족 조건 수 / 선택 조건 수`로 추천 순위 계산
- 행정동 단계구분도, 선택 시설 마커, 추천 TOP 3 동시 갱신
- 행정동별 충족·미충족 조건, 교통 접근성, 평균 주거비, 시설 목록 표시
- 네이버 지도 길찾기와 네이버부동산 외부 연결
- 모바일·태블릿·데스크톱 반응형 레이아웃

## 데이터

`scripts/build_life_fit_data.py`가 제공된 `siheung_life_infra.csv`를 읽어 배포용 `data/processed/life_fit.json`을 만듭니다. 원본 CSV는 수정하지 않습니다.

```bash
python3 scripts/build_life_fit_data.py
```

생활시설은 제공된 카카오 장소 수집본을 사용합니다. 현재 비교 범위는 경계 데이터가 준비된 배곧동, 정왕1동, 정왕2동, 대야동, 신천동, 은행동입니다. 주거비와 버스 접근성은 UI·추천 흐름 검증을 위한 프로토타입 요약값이므로 실제 서비스 배포 전 공공데이터 집계로 교체해야 합니다.

## 로컬 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다. 상태 확인은 `http://127.0.0.1:8000/health`, 데이터 API는 `http://127.0.0.1:8000/api/life-fit`입니다.

## 프로젝트 구조

```text
app/main.py                         FastAPI 서버와 API
static/index.html                   페이지 구조
static/css/style.css                반응형 디자인
static/js/app.js                    추천·필터·지도 상호작용
scripts/build_life_fit_data.py      원본 시설 CSV 정제
data/processed/life_fit.json        브라우저용 정제 데이터
static/data/siheung_dong_boundaries.geojson  행정동 경계 참고 데이터
```

## 추천 계산 원칙

각 카테고리는 문서에 정의된 최소 시설 수를 따로 사용합니다. 선택한 도보권에서 기준을 충족한 카테고리 수가 많은 행정동을 우선하며, 동률이면 선택 시설의 추정 개수가 많은 행정동을 먼저 보여줍니다. 서로 다른 시설의 개수를 하나의 점수로 합산하거나 임의의 가중치를 적용하지 않습니다.
