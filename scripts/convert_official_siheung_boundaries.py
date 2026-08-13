"""시흥시 제공 행정동 SHP를 웹 지도용 GeoJSON으로 변환한다.

공식 원본: 경기도 시흥시_행정동경계_20250610 (공공데이터포털 15104305)
SHP의 실제 기준일은 2023-08-01이며, 거북섬동을 포함한 20개 행정동이다.

실행 예시:
    PYTHONPATH=/tmp/siheung-geo-runtime python scripts/convert_official_siheung_boundaries.py \
      /tmp/siheung-boundaries.zip

변환에는 `pyshp`, `pyproj`가 필요하다. 이 라이브러리는 배포 서버가 아닌
데이터 갱신 작업에서만 필요하다.
"""
from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import shapefile
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "data" / "siheung_admin_dong_boundaries.geojson"

AREA_IDS = {
    "거북섬동": "geobukseom",
    "대야동": "daeya",
    "신천동": "sincheon",
    "신현동": "sinhyeon",
    "은행동": "eunhaeng",
    "매화동": "maehwa",
    "목감동": "mokgam",
    "과림동": "gwarim",
    "정왕1동": "jeongwang1",
    "정왕2동": "jeongwang2",
    "정왕3동": "jeongwang3",
    "정왕4동": "jeongwang4",
    "정왕본동": "jeongwangbon",
    "능곡동": "neunggok",
    "군자동": "gunja",
    "월곶동": "wolgot",
    "연성동": "yeonseong",
    "장곡동": "janggok",
    "배곧1동": "baegot1",
    "배곧2동": "baegot2",
}


def extract_shape_files(archive: Path) -> Path:
    """한글 파일명 ZIP에서도 확장자만 이용해 안전한 영문 파일명으로 꺼낸다."""
    directory = Path(tempfile.mkdtemp(prefix="siheung-official-boundary-"))
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            extension = Path(item.filename).suffix.lower()
            if extension in {".shp", ".shx", ".dbf", ".prj", ".cpg"}:
                (directory / f"boundary{extension}").write_bytes(source.read(item))
    return directory


def polygon_coordinates(shape: shapefile.Shape, transformer: Transformer) -> list[list[list[float]]]:
    """SHP Polygon의 각 part를 WGS84 GeoJSON 좌표로 변환한다."""
    parts = list(shape.parts) + [len(shape.points)]
    polygons: list[list[list[float]]] = []
    for start, end in zip(parts, parts[1:]):
        ring = []
        for x, y in shape.points[start:end]:
            lng, lat = transformer.transform(x, y)
            ring.append([round(lng, 7), round(lat, 7)])
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        if len(ring) >= 4:
            polygons.append(ring)
    return polygons


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python scripts/convert_official_siheung_boundaries.py 공식경계.zip")
    archive = Path(sys.argv[1]).expanduser().resolve()
    if not archive.exists():
        raise SystemExit(f"원본 ZIP을 찾지 못했습니다: {archive}")

    directory = extract_shape_files(archive)
    reader = shapefile.Reader(str(directory / "boundary.shp"), encoding="utf-8", encodingErrors="replace")
    transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    features = []
    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        # 공식 DBF의 한글 필드명은 10-byte 제한으로 잘릴 수 있으므로 값 순서를 사용한다.
        name = str(list(shape_record.record)[2]).strip()
        area_id = AREA_IDS.get(name)
        if not area_id:
            raise SystemExit(f"알 수 없는 행정동명: {name}")
        rings = polygon_coordinates(shape_record.shape, transformer)
        geometry = {
            "type": "Polygon" if len(rings) == 1 else "MultiPolygon",
            "coordinates": [rings[0]] if len(rings) == 1 else [[ring] for ring in rings],
        }
        features.append({
            "type": "Feature",
            "properties": {
                "id": area_id,
                "name": name,
                "data_area_id": area_id,
                "adm_cd": str(list(shape_record.record)[1]),
                "source": "경기도 시흥시 행정동경계_20250610 (공공데이터포털 15104305)",
                "source_standard_date": str(list(shape_record.record)[0]),
            },
            "geometry": geometry,
        })
    if len(features) != 20:
        raise SystemExit(f"행정동 수가 20개가 아닙니다: {len(features)}")
    OUTPUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(features)} official administrative dongs")
    print(", ".join(feature["properties"]["name"] for feature in features))


if __name__ == "__main__":
    main()
