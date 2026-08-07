# 1인가구 인프라 지도 — 데이터 소스 레퍼런스

> **작성일**: 2026-08-06  
> **작성자**: ch  
> **목적**: 경기도 1인가구 생활 인프라 지도 프로젝트의 데이터 수집 방법 정리

---

## 프로젝트 개요

경기도 1인가구를 위한 생활 인프라 지도. 코인세탁방, 공공체육시설, 약국 등 1인가구 생활에 필요한 시설 데이터를 지도에 시각화하는 프로젝트.

**주요 레이어**: 코인세탁방 · 약국 · 공공체육시설 · 레저스포츠시설 · 캠핑장 · 낚시터 · 문화행사 · 백년가게

---

## 범례

| 아이콘 | 의미 |
|--------|------|
| ✅ | REST API 수집 가능 (인증키 필요) |
| 📁 | 파일 다운로드 가능 |
| 🔓 | sample key로 테스트 가능 |
| ⚠️ | 갱신 주기 없음 (1회성 데이터) |
| ❌ | 직접 공식 API 없음 (대안 필요) |

---

## 경기도 공공데이터 공통 사항

### API 기본 정보
- **포털**: [경기데이터드림](https://data.gg.go.kr)
- **API 엔드포인트 기본 URL**: `https://openapi.gg.go.kr/`
- **인증키 신청**: https://data.gg.go.kr (회원가입 후 마이페이지 → 인증키 신청)
- **응답 형식**: XML (기본값) 또는 JSON (`Type=json` 파라미터 추가)
- **요청 제한**: 인증키 발급 후 제한 없음 (sample key는 페이지당 5건 고정)

### 공통 파라미터

| 파라미터 | 타입 | 설명 | 기본값 |
|---------|------|------|--------|
| `KEY` | STRING | 인증키 | `sample` (테스트용) |
| `Type` | STRING | 응답 형식 | `xml` |
| `pIndex` | INTEGER | 페이지 번호 | `1` |
| `pSize` | INTEGER | 페이지당 건수 | `100` |

### 인증키 발급 방법

1. https://data.gg.go.kr 접속 → 회원가입
2. 로그인 후 상단 메뉴 → **개방** → 원하는 데이터셋 선택
3. OPEN API 탭 → **인증키 신청** 버튼 클릭
4. 신청서 작성 (활용 목적 기재) → 즉시 또는 1~2일 내 발급

---

## 1. 약국 ✅ 📁

| 항목 | 내용 |
|------|------|
| **데이터명** | 약국 현황 |
| **제공 기관** | 경기도 AI데이터행정과 |
| **출처 URL** | https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=PIJI8PESB5U6V7U3LZ5O28053826&infSeq=3 |
| **API 엔드포인트** | `https://openapi.gg.go.kr/ParmacyInfo` |
| **갱신 주기** | 월간 |
| **인증키 필요** | ✅ 필요 (sample key 테스트 가능) |
| **응답 형식** | JSON / XML |
| **수집 방법** | REST API 또는 Sheet 다운로드 |

### 주요 출력 컬럼

| 컬럼명 | 설명 |
|--------|------|
| `SIGUN_NM` | 시군명 |
| `INST_NM` | 약국명 |
| `REPRSNT_TELNO` | 대표전화번호 |
| `REFINE_ROADNM_ADDR` | 도로명주소 |
| `REFINE_LOTNO_ADDR` | 지번주소 |
| `REFINE_WGS84_LAT` | 위도 (WGS84) |
| `REFINE_WGS84_LOGT` | 경도 (WGS84) |
| `MON_BEGIN_TREAT_TM` ~ `HOLIDAY_END_TREAT_TM` | 요일별·공휴일 운영시간 |

### 추가 요청 파라미터

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `SIGUN_NM` | STRING (선택) | 시군명 필터 (예: `수원시`) |
| `INST_NM` | STRING (선택) | 약국명 검색 |
| `SIGUN_CD` | STRING (선택) | 시군코드 |

### Python 예시 코드

```python
import requests

API_KEY = "여기에_발급받은_인증키_입력"  # sample → 실제 키로 교체
BASE_URL = "https://openapi.gg.go.kr/ParmacyInfo"

def fetch_pharmacies(sigun_nm=None, page=1, page_size=1000):
    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": page,
        "pSize": page_size,
    }
    if sigun_nm:
        params["SIGUN_NM"] = sigun_nm
    
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    # 응답 구조: {"ParmacyInfo": [{"head": [...]}, {"row": [...]}]}
    rows = data["ParmacyInfo"][1]["row"]
    return rows

# 예시: 수원시 약국 전체 조회
pharmacies = fetch_pharmacies(sigun_nm="수원시")
print(f"수원시 약국 수: {len(pharmacies)}")
for p in pharmacies[:3]:
    print(f"  {p['INST_NM']} | {p['REFINE_ROADNM_ADDR']} | 위도:{p['REFINE_WGS84_LAT']} 경도:{p['REFINE_WGS84_LOGT']}")
```

---

## 2. 공공체육시설 ✅ 📁

| 항목 | 내용 |
|------|------|
| **데이터명** | 경기도 체육시설 현황 |
| **제공 기관** | 경기도 |
| **출처 URL** | https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=YG4B0YBL1L8L2O63TCJT35091487&infSeq=3 |
| **API 엔드포인트** | `https://openapi.gg.go.kr/TBGGPHSTRNFACLTM` |
| **갱신 주기** | 수시 |
| **인증키 필요** | ✅ 필요 |
| **응답 형식** | JSON / XML |
| **수집 방법** | REST API |

### 주요 출력 컬럼

| 컬럼명 | 설명 |
|--------|------|
| `SI_DESC` | 시설명 |
| `FACLT_DIV_NM` | 시설구분명 |
| `INDUTYPE_NM` | 업종명 (체육관, 수영장 등) |
| `FACLT_TYPE_NM` | 시설유형명 |
| `FACLT_STATE_NM` | 시설상태명 |
| `REFINE_ROADNM_ADDR` | 도로명주소 |
| `REFINE_WGS84_LAT` | 위도 |
| `REFINE_WGS84_LOGT` | 경도 |
| `FACLT_TELNO` | 시설전화번호 |
| `SIDO_NM` / `SIGNGU_NM` | 시도명 / 시군구명 |
| `INOUTDR_DIV_NM` | 실내외구분 |
| `LIVELH_OPENPUBL_YN` | 생활체육 공개여부 |

### Python 예시 코드

```python
import requests

API_KEY = "여기에_발급받은_인증키_입력"
BASE_URL = "https://openapi.gg.go.kr/TBGGPHSTRNFACLTM"

def fetch_sports_facilities(page=1, page_size=1000):
    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": page,
        "pSize": page_size,
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    data = resp.json()
    rows = data["TBGGPHSTRNFACLTM"][1]["row"]
    return rows

facilities = fetch_sports_facilities()
print(f"체육시설 수: {len(facilities)}")
```

---

## 3. 낚시터 ✅ 📁

| 항목 | 내용 |
|------|------|
| **데이터명** | 낚시터 현황 (제공표준) |
| **제공 기관** | 가평군 외 14개 기관 |
| **출처 URL** | https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=R7KLK10JTQ9830864S6A21731572&infSeq=3 |
| **API 엔드포인트** | `https://openapi.gg.go.kr/FISHPLCINFO` |
| **갱신 주기** | 연간 |
| **인증키 필요** | ✅ 필요 |
| **응답 형식** | JSON / XML |
| **수집 방법** | REST API |

### 주요 출력 컬럼

| 컬럼명 | 설명 |
|--------|------|
| `SIGUN_NM` / `SIGUN_CD` | 시군명 / 시군코드 |
| `FACLT_NM` | 낚시터명 |
| `FACLT_DIV_NM` | 시설구분명 |
| `REFINE_ROADNM_ADDR` | 도로명주소 |
| `REFINE_WGS84_LAT` / `REFINE_WGS84_LOGT` | 위도/경도 |
| `FACLT_TELNO` | 시설전화번호 |
| `WTR_AR` | 수면적 |
| `FISHKIND_NM` | 어종명 |
| `ACEPTNC_POSBL_PSN_CNT` | 수용가능인원수 |
| `CHRG_INFO` | 요금정보 |
| `CONVNCE_FACLT_INFO` | 편의시설정보 |

### Python 예시 코드

```python
import requests

API_KEY = "여기에_발급받은_인증키_입력"
BASE_URL = "https://openapi.gg.go.kr/FISHPLCINFO"

def fetch_fishing_spots(sigun_nm=None, page=1, page_size=500):
    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": page,
        "pSize": page_size,
    }
    if sigun_nm:
        params["SIGUN_NM"] = sigun_nm
    
    resp = requests.get(BASE_URL, params=params, timeout=30)
    data = resp.json()
    rows = data["FISHPLCINFO"][1]["row"]
    return rows

spots = fetch_fishing_spots()
print(f"낚시터 수: {len(spots)}")
```

---

## 4. 야영(캠핑)장 ✅ 📁

| 항목 | 내용 |
|------|------|
| **데이터명** | 야영(캠핑)장 시설 현황 |
| **제공 기관** | 가평군 외 18개 기관 |
| **출처 URL** | https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=6243I631A7C7L7M0JR1B21715119&infSeq=1 |
| **갱신 주기** | 연간 |
| **인증키 필요** | ✅ 필요 (OPEN API 탭 확인) |
| **응답 형식** | JSON / XML / 파일 다운로드 |
| **수집 방법** | REST API 또는 Sheet 다운로드 |

### 주요 출력 컬럼

| 컬럼명 | 설명 |
|--------|------|
| `야영(캠핑)장명` | 캠핑장 이름 |
| `야영(캠핑)장구분` | 야영장/자동차야영장/글램핑 등 |
| `위도` / `경도` | GPS 좌표 |
| `소재지도로명주소` | 도로명주소 |
| `야영장전화번호` | 연락처 |
| `야영사이트수` | 사이트 개수 |
| `1일최대수용인원수` | 최대 수용 인원 |
| `이용요금` | 요금 정보 |
| `편의시설` | 샤워실 등 |
| `이용시간` | 운영 시간 |

### Python 예시 코드 (파일 다운로드 방식)

```python
import requests
import pandas as pd
from io import StringIO

# Sheet 탭 다운로드 버튼 → CSV/Excel 형식으로 직접 다운로드 가능
# 또는 OPEN API 엔드포인트 사용 (인증키 발급 후 확인)

# 공공데이터포털 원본 API 활용 (전국 야영장 데이터)
API_KEY = "공공데이터포털_발급_키"
url = "https://apis.data.go.kr/B551011/GoCamping/basedList"

params = {
    "serviceKey": API_KEY,
    "numOfRows": 1000,
    "pageNo": 1,
    "MobileOS": "ETC",
    "MobileApp": "TestApp",
    "_type": "json",
}
resp = requests.get(url, params=params, timeout=30)
data = resp.json()
items = data["response"]["body"]["items"]["item"]
# 경기도만 필터
gyeonggi = [x for x in items if x.get("doNm") == "경기"]
print(f"경기도 캠핑장 수: {len(gyeonggi)}")
```

> **팁**: 전국 야영장 데이터는 [한국관광공사 고캠핑 API](https://www.data.go.kr/data/15101933/openapi.do) (data.go.kr)에서도 수집 가능하며, 경기도 필터링 후 활용 추천.

---

## 5. 레저스포츠시설 ✅ 📁 ⚠️

| 항목 | 내용 |
|------|------|
| **데이터명** | 경기도 레저스포츠 시설 현황 |
| **제공 기관** | 경기도 AI데이터행정과 |
| **출처 URL** | https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=EOLX6QV7RPE21TD55XSP31115603&infSeq=1 |
| **갱신 주기** | 주기없음 (2021-03-05 기준, 정적 데이터) |
| **인증키 필요** | ✅ 필요 (OPEN API 탭 확인) |
| **응답 형식** | JSON / XML / 파일 다운로드 |
| **수집 방법** | REST API 또는 Sheet 다운로드 (파일 권장) |

> ⚠️ **주의**: 갱신 주기 없음 — 2021년 이후 미갱신. 오토캠핑장, 수상레저, 글램핑 등 야외 레저시설 포함.

### 주요 출력 컬럼

| 컬럼명 | 설명 |
|--------|------|
| `시군명` | 시군 이름 |
| `시설명` | 레저스포츠 시설명 |
| `전화번호` | 연락처 |
| `정제도로명주소` | 도로명주소 |
| `정제WGS84위도` / `정제WGS84경도` | 위경도 |

### 수집 방법 (파일 다운로드)

경기데이터드림 해당 페이지 → **Sheet 탭** → **다운로드** 버튼 → Excel/CSV 저장

```python
import pandas as pd

# 다운로드한 파일 로드 (Excel 형식)
df = pd.read_excel("경기도_레저스포츠_시설_현황.xlsx")
print(df.columns.tolist())
print(df.head())
```

---

## 6. 경기도 문화 행사/축제 📁

| 항목 | 내용 |
|------|------|
| **데이터명** | 경기도 문화 행사 현황 |
| **제공 기관** | 경기문화재단 |
| **출처 URL** | https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=ZEC3WU7ANKZDLGIFEIHA32825043&infSeq=1 |
| **갱신 주기** | 수시 |
| **인증키 필요** | ❌ 불필요 (Sheet 다운로드) |
| **응답 형식** | CSV / Excel (파일 다운로드) |
| **수집 방법** | Sheet 탭 → 다운로드 |
| **라이선스** | 공공누리 3유형 (출처표시, 변경금지) |

> ℹ️ OPEN API 탭이 존재하나, Sheet 탭의 직접 다운로드가 더 간편.  
> 이 데이터는 **위도/경도 미포함** — 행사 장소명 기준 지오코딩 필요.

### 주요 컬럼

| 컬럼명 | 설명 |
|--------|------|
| `기관명` | 주관 기관 |
| `제목` | 행사명 |
| `분류` | 행사/공연/전시 등 |
| `시작일자` / `종료일자` | 행사 기간 (YYYYMMDD) |
| `시간` | 행사 시간 |
| `비용` | 입장료 |
| `전화번호` | 문의처 |
| `주최기관명` | 주최 기관 |
| `URL` | 상세 URL |
| `이미지URL` | 포스터 이미지 |

### Python 예시 코드

```python
import pandas as pd

# 파일 다운로드 후 로드
df = pd.read_excel("경기도_문화_행사_현황.xlsx")

# 날짜 파싱
df["시작일자"] = pd.to_datetime(df["시작일자"], format="%Y%m%d", errors="coerce")
df["종료일자"] = pd.to_datetime(df["종료일자"], format="%Y%m%d", errors="coerce")

# 현재 진행중인 행사 필터
from datetime import datetime
today = datetime.now()
active = df[(df["시작일자"] <= today) & (df["종료일자"] >= today)]
print(f"현재 진행중인 행사: {len(active)}건")
```

> **지오코딩 필요**: 행사 장소 주소 → 위경도 변환에 카카오맵 API 또는 공공 지오코딩 API 활용.

---

## 7. 백년가게 📁 ⚠️

| 항목 | 내용 |
|------|------|
| **데이터명** | 백년가게 지정현황 |
| **제공 기관** | 경기도 AI데이터행정과 |
| **출처 URL** | https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=6XGZIF1N2RBQF7DTIIU831075013&infSeq=1 |
| **갱신 주기** | 주기없음 (2022-11-24 기준) |
| **인증키 필요** | ✅ 필요 (OPEN API 탭 확인) |
| **응답 형식** | JSON / XML / 파일 다운로드 |
| **수집 방법** | REST API 또는 Sheet 다운로드 |

> ⚠️ **주의**: 2022년 11월 이후 미갱신. 30년 이상 업력의 우수 소상공인.  
> 최신 목록: [중소기업벤처부 홈페이지](https://www.sbiz.or.kr/hdst/main/ohndMarketList.do) 참고.

### 주요 컬럼

| 컬럼명 | 설명 |
|--------|------|
| `구분` | 업종 (음식점업, 도소매업 등) |
| `업체명` | 가게 이름 |
| `업력(창업년도)` | 창업 연도 및 업력 |
| `전화번호` | 연락처 |
| `정제도로명주소` | 도로명주소 |
| `정제WGS84위도` / `정제WGS84경도` | 위경도 |

---

## 8. 코인세탁방 ❌ (대안 수집 방법)

> 공공데이터포털(data.go.kr)에 경기도 코인세탁방 전용 공개 API가 존재하지 않음.  
> 아래 3가지 대안을 활용.

### 대안 1: 행정안전부 지방행정 인허가 데이터 (추천 ⭐)

| 항목 | 내용 |
|------|------|
| **출처** | [공공데이터포털 - 지방행정인허가](https://www.data.go.kr/data/15096028/fileData.do) |
| **분류** | 세탁업 → 코인세탁 필터 |
| **형식** | CSV 파일 다운로드 |
| **갱신** | 분기별 |

```python
import pandas as pd
import requests

# 지방행정인허가 데이터 - 세탁업 파일 다운로드 (전국)
# data.go.kr에서 "세탁업" 검색 → CSV 다운로드
# 또는 OpenAPI 활용

API_KEY = "공공데이터포털_발급_키"  # data.go.kr에서 발급
url = "https://api.odcloud.kr/api/15096028/v1/uddi:a2ce5c37-cf68-4978-a9e6-4609f5bc5fbe"

params = {
    "page": 1,
    "perPage": 1000,
    "serviceKey": API_KEY,
    "returnType": "json",
    "cond[APPL_YMD::GTE]": "20200101",  # 영업 상태 필터
}
resp = requests.get(url, params=params)
data = resp.json()

# 세탁업 중 코인세탁방 필터 (업태명 또는 상호명 기준)
items = data.get("data", [])
coin_laundry = [
    x for x in items 
    if "코인" in str(x.get("BSNS_SITE_NM", "")) 
    or "세탁" in str(x.get("BSNS_SITE_NM", ""))
]
# 경기도 필터
gyeonggi = [x for x in coin_laundry if "경기" in str(x.get("REFINE_LOTNO_ADDR", ""))]
print(f"경기도 코인세탁방 추정 수: {len(gyeonggi)}")
```

### 대안 2: 카카오맵 로컬 API (키워드 검색)

| 항목 | 내용 |
|------|------|
| **출처** | [카카오 개발자센터](https://developers.kakao.com) |
| **API** | 키워드로 장소 검색 (`/v2/local/search/keyword.json`) |
| **인증** | REST API 키 (무료 발급, 일 30만 건) |
| **형식** | JSON |
| **특이사항** | 위경도 포함, 최대 45건/페이지, 페이지네이션 필요 |

#### 카카오맵 REST API 키 발급 방법

1. https://developers.kakao.com 접속 → 카카오 계정 로그인
2. **내 애플리케이션** → **애플리케이션 추가하기**
3. 앱 이름 입력 후 생성 → **앱 키** → **REST API 키** 복사

```python
import requests
import time

KAKAO_API_KEY = "여기에_REST_API_키_입력"

def search_kakao_local(query, x=None, y=None, radius=20000, page=1):
    """카카오 키워드 검색 API"""
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {
        "query": query,
        "size": 15,
        "page": page,
    }
    if x and y:
        params.update({"x": x, "y": y, "radius": radius, "sort": "distance"})
    
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    return resp.json()

def fetch_all_coin_laundry_gyeonggi():
    """경기도 주요 시군별 코인세탁방 수집"""
    # 경기도 주요 도시 중심 좌표 (위도, 경도)
    cities = {
        "수원시": (37.2636, 127.0286),
        "용인시": (37.2411, 127.1775),
        "성남시": (37.4201, 127.1260),
        "고양시": (37.6584, 126.8320),
        "부천시": (37.5034, 126.7660),
        "안산시": (37.3219, 126.8309),
        "남양주시": (37.6360, 127.2163),
        "화성시": (37.1997, 126.8314),
        "평택시": (36.9921, 127.1128),
        "의정부시": (37.7382, 127.0337),
        "안양시": (37.3943, 126.9568),
        "시흥시": (37.3800, 126.8031),
        "파주시": (37.7600, 126.7797),
        "김포시": (37.6152, 126.7153),
        "광주시": (37.4296, 127.2558),
        "군포시": (37.3614, 126.9352),
        "하남시": (37.5397, 127.2147),
        "오산시": (37.1498, 127.0773),
        "이천시": (37.2720, 127.4351),
        "양주시": (37.7854, 127.0457),
    }
    
    all_results = []
    seen_ids = set()
    
    for city, (lat, lon) in cities.items():
        print(f"  {city} 수집 중...")
        for page in range(1, 4):  # 최대 3페이지
            result = search_kakao_local(
                "코인세탁방",
                x=lon, y=lat,
                radius=10000,
                page=page
            )
            items = result.get("documents", [])
            if not items:
                break
            
            for item in items:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    all_results.append({
                        "id": item["id"],
                        "시설명": item["place_name"],
                        "주소": item["road_address_name"] or item["address_name"],
                        "전화번호": item.get("phone", ""),
                        "경도": float(item["x"]),
                        "위도": float(item["y"]),
                        "카카오URL": item.get("place_url", ""),
                    })
            
            if result.get("meta", {}).get("is_end"):
                break
            time.sleep(0.3)  # API 호출 간격
    
    return all_results

# 실행
laundries = fetch_all_coin_laundry_gyeonggi()
print(f"\n경기도 코인세탁방 수집 결과: {len(laundries)}개소")
```

### 대안 3: 네이버 지도 API

| 항목 | 내용 |
|------|------|
| **출처** | [네이버 클라우드 플랫폼](https://www.ncloud.com/product/applicationService/maps) |
| **API** | Maps Geocoding / Places |
| **인증** | Client ID + Client Secret (무료 티어 있음) |
| **특이사항** | 카카오맵보다 데이터 풍부도 다를 수 있음 |

---

## 수집 전략 요약

| 카테고리 | 수집 방법 | 위경도 포함 | 갱신 주기 | 난이도 | 우선순위 |
|---------|---------|-----------|---------|--------|---------|
| 약국 | ✅ REST API | ✅ | 월간 | ⭐ 쉬움 | 🔴 높음 |
| 공공체육시설 | ✅ REST API | ✅ | 수시 | ⭐ 쉬움 | 🔴 높음 |
| 낚시터 | ✅ REST API | ✅ | 연간 | ⭐ 쉬움 | 🟡 중간 |
| 캠핑장 | ✅ REST API / 파일 | ✅ | 연간 | ⭐ 쉬움 | 🟡 중간 |
| 레저스포츠시설 | 📁 파일 다운로드 | ✅ | ⚠️ 없음 | ⭐ 쉬움 | 🟢 낮음 |
| 문화행사 | 📁 파일 다운로드 | ❌ (지오코딩 필요) | 수시 | ⭐⭐ 보통 | 🟡 중간 |
| 백년가게 | 📁 파일 다운로드 | ✅ | ⚠️ 없음 | ⭐ 쉬움 | 🟢 낮음 |
| 코인세탁방 | 카카오맵 API | ✅ | 실시간 | ⭐⭐⭐ 어려움 | 🔴 높음 |

---

## 통합 데이터 수집 스크립트 구조

```python
# scripts/collect_all.py
import requests
import pandas as pd
import json
import os

GG_API_KEY = os.environ.get("GG_API_KEY")       # 경기데이터드림 인증키
KAKAO_API_KEY = os.environ.get("KAKAO_API_KEY")  # 카카오 REST API 키

DATASETS = {
    "pharmacy": {
        "url": "https://openapi.gg.go.kr/ParmacyInfo",
        "key": "ParmacyInfo",
    },
    "sports": {
        "url": "https://openapi.gg.go.kr/TBGGPHSTRNFACLTM",
        "key": "TBGGPHSTRNFACLTM",
    },
    "fishing": {
        "url": "https://openapi.gg.go.kr/FISHPLCINFO",
        "key": "FISHPLCINFO",
    },
}

def fetch_gg_api(url, api_key_name, page_size=1000):
    """경기도 공공 API 전체 페이지 수집"""
    all_rows = []
    page = 1
    
    while True:
        params = {
            "KEY": GG_API_KEY,
            "Type": "json",
            "pIndex": page,
            "pSize": page_size,
        }
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        try:
            head = data[api_key_name][0]["head"]
            total = int(head[0]["list_total_count"])
            rows = data[api_key_name][1]["row"]
            all_rows.extend(rows)
            print(f"  페이지 {page} 수집: {len(rows)}건 (총 {total}건)")
            
            if len(all_rows) >= total:
                break
            page += 1
        except (KeyError, IndexError) as e:
            print(f"  오류: {e}")
            break
    
    return all_rows

def save_geojson(rows, lat_key, lon_key, props_keys, output_path):
    """GeoJSON 형식으로 저장"""
    features = []
    for row in rows:
        try:
            lat = float(row[lat_key])
            lon = float(row[lon_key])
            if not (33 <= lat <= 39 and 124 <= lon <= 132):
                continue  # 유효하지 않은 좌표 제외
            
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {k: row.get(k, "") for k in props_keys},
            }
            features.append(feature)
        except (ValueError, TypeError):
            continue
    
    geojson = {"type": "FeatureCollection", "features": features}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"  저장 완료: {output_path} ({len(features)}건)")

if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/geojson", exist_ok=True)
    
    # 약국 수집
    print("약국 수집 중...")
    pharmacies = fetch_gg_api(
        DATASETS["pharmacy"]["url"],
        DATASETS["pharmacy"]["key"]
    )
    save_geojson(
        pharmacies,
        lat_key="REFINE_WGS84_LAT",
        lon_key="REFINE_WGS84_LOGT",
        props_keys=["INST_NM", "REFINE_ROADNM_ADDR", "REPRSNT_TELNO", "SIGUN_NM"],
        output_path="data/geojson/pharmacies.geojson"
    )
```

---

## 지도 시각화 추천 스택

### 라이브러리 비교

| 라이브러리 | 장점 | 단점 | 추천 용도 |
|-----------|------|------|---------|
| **Folium** | 쉬운 사용, Leaflet.js 기반, HTML 출력 | 대용량 데이터 느림 | 프로토타입, 소규모 데이터 |
| **Plotly Express** | 인터랙티브, 데이터분석 통합 | 맵박스 키 필요 (일부) | 대시보드, 통계 분석 |
| **Kepler.gl** | 대용량 처리, 3D 지원, 고성능 | 설정 복잡 | 대용량 데이터, 고급 시각화 |
| **PyDeck** | GPU 렌더링, 대용량 | Python 사용성 복잡 | 수십만 건 이상 |

### **추천: Folium (프로토타입) → Kepler.gl (최종)**

```python
import folium
from folium.plugins import MarkerCluster
import pandas as pd
import json

# 색상 코드 (레이어별)
LAYER_COLORS = {
    "pharmacy":     "#e74c3c",   # 🔴 빨강 - 약국
    "sports":       "#2ecc71",   # 🟢 초록 - 공공체육시설
    "fishing":      "#3498db",   # 🔵 파랑 - 낚시터
    "camping":      "#27ae60",   # 🟩 진초록 - 캠핑장
    "leisure":      "#f39c12",   # 🟠 주황 - 레저스포츠
    "event":        "#9b59b6",   # 🟣 보라 - 문화행사
    "century_shop": "#e67e22",   # 🟤 갈색 - 백년가게
    "coin_laundry": "#1abc9c",   # 🩵 청록 - 코인세탁방
}

# 아이콘 설정 (Font Awesome)
LAYER_ICONS = {
    "pharmacy":     ("pills", "red"),
    "sports":       ("dumbbell", "green"),
    "fishing":      ("fish", "blue"),
    "camping":      ("campground", "darkgreen"),
    "leisure":      ("running", "orange"),
    "event":        ("calendar", "purple"),
    "century_shop": ("store", "brown"),
    "coin_laundry": ("tshirt", "cadetblue"),
}

def create_map(center=[37.4138, 127.5183], zoom=9):
    """경기도 중심 기본 지도 생성"""
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",  # 밝은 배경 지도
    )
    return m

def add_layer(m, geojson_path, layer_name, color, icon_name):
    """GeoJSON 레이어 추가"""
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)
    
    cluster = MarkerCluster(name=layer_name).add_to(m)
    
    for feature in data["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        props = feature["properties"]
        
        # 팝업 내용
        popup_html = "<br>".join(
            f"<b>{k}</b>: {v}" 
            for k, v in props.items() 
            if v
        )
        
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=color, icon=icon_name, prefix="fa"),
        ).add_to(cluster)
    
    return m

# 사용 예시
if __name__ == "__main__":
    m = create_map()
    
    # 레이어 추가
    add_layer(m, "data/geojson/pharmacies.geojson", "약국", "red", "plus")
    add_layer(m, "data/geojson/sports.geojson", "공공체육시설", "green", "futbol-o")
    
    # 레이어 컨트롤 추가
    folium.LayerControl(collapsed=False).add_to(m)
    
    # HTML 저장
    m.save("output/gyeonggi_1person_map.html")
    print("지도 저장 완료: output/gyeonggi_1person_map.html")
```

---

## 환경 설정 및 의존성

```bash
# 필수 패키지 설치
pip install requests pandas folium geopandas

# 선택 패키지 (고급 시각화)
pip install keplergl plotly pydeck

# 환경 변수 설정 (.env 파일)
GG_API_KEY=경기데이터드림_발급키
KAKAO_API_KEY=카카오_REST_API_키
DATA_GO_KR_KEY=공공데이터포털_발급키
```

---

## 참고 링크

| 분류 | 링크 |
|------|------|
| 경기데이터드림 | https://data.gg.go.kr |
| 공공데이터포털 | https://www.data.go.kr |
| 카카오 개발자 | https://developers.kakao.com |
| 네이버 클라우드 | https://www.ncloud.com |
| 중소벤처기업부 백년가게 | https://www.sbiz.or.kr/hdst/main/ohndMarketList.do |
| 한국관광공사 고캠핑 API | https://www.data.go.kr/data/15101933/openapi.do |
| Folium 문서 | https://python-visualization.github.io/folium |
| Kepler.gl Python | https://docs.kepler.gl/docs/keplergl-jupyter |
