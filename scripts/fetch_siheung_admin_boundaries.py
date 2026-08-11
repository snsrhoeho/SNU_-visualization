"""OpenStreetMap 행정동 관계를 시흥시 전체 행정동 GeoJSON으로 저장한다.

실행 시점에만 Overpass API를 호출한다. 배포 웹은 생성된 GeoJSON만 읽는다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "data" / "siheung_admin_dong_boundaries.geojson"

RELATIONS = {
    12926904: ("baegot1", "배곧1동", "baegot"), 12926905: ("baegot2", "배곧2동", "baegot"),
    13374813: ("jeongwang1", "정왕1동", "jeongwang1"), 13375012: ("jeongwang2", "정왕2동", "jeongwang2"),
    13375013: ("jeongwang3", "정왕3동", None), 13375014: ("jeongwang4", "정왕4동", None), 13375015: ("jeongwangbon", "정왕본동", None),
    13375077: ("neunggok", "능곡동", None), 13375078: ("gunja", "군자동", None), 13375079: ("janggok", "장곡동", None),
    13375080: ("wolgot", "월곶동", None), 13375226: ("yeonseong", "연성동", None), 13375227: ("sinhyeon", "신현동", None),
    13375243: ("sincheon", "신천동", "sincheon"), 13375641: ("daeya", "대야동", "daeya"),
    13375642: ("eunhaeng", "은행동", "eunhaeng"), 13375643: ("gwarim", "과림동", None),
    13375644: ("maehwa", "매화동", None), 13375645: ("mokgam", "목감동", None),
}


def points_equal(a: list[list[float]], b: list[list[float]]) -> bool:
    return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9


def stitch(segments: list[list[list[float]]]) -> list[list[list[float]]]:
    """OSM의 분할된 outer way를 GeoJSON polygon ring으로 연결한다."""
    pending = [segment[:] for segment in segments if len(segment) > 1]
    rings: list[list[list[float]]] = []
    while pending:
        ring = pending.pop(0)
        while not points_equal(ring[0], ring[-1]):
            for index, segment in enumerate(pending):
                if points_equal(ring[-1], segment[0]):
                    ring.extend(segment[1:]); pending.pop(index); break
                if points_equal(ring[-1], segment[-1]):
                    ring.extend(list(reversed(segment[:-1]))); pending.pop(index); break
                if points_equal(ring[0], segment[-1]):
                    ring = segment[:-1] + ring; pending.pop(index); break
                if points_equal(ring[0], segment[0]):
                    ring = list(reversed(segment[1:])) + ring; pending.pop(index); break
            else:
                raise ValueError("OSM outer way를 하나의 경계로 연결하지 못했습니다.")
        rings.append(ring)
    return rings


def fetch_relation(relation_id: int) -> dict:
    response = subprocess.run(
        ["curl", "-k", "-sS", f"https://www.openstreetmap.org/api/0.6/relation/{relation_id}/full.json"],
        check=True, capture_output=True, text=True, timeout=120,
    )
    elements = json.loads(response.stdout)["elements"]
    nodes = {item["id"]: item for item in elements if item["type"] == "node"}
    ways = {item["id"]: item for item in elements if item["type"] == "way"}
    relation = next(item for item in elements if item["type"] == "relation" and item["id"] == relation_id)
    members = []
    for member in relation["members"]:
        if member["type"] != "way" or member["ref"] not in ways:
            continue
        members.append({**member, "geometry": [{"lon": nodes[node_id]["lon"], "lat": nodes[node_id]["lat"]} for node_id in ways[member["ref"]]["nodes"]]})
    return {**relation, "members": members}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", default=[], help="Overpass JSON 응답 파일 (여러 번 지정 가능)")
    args = parser.parse_args()
    supplied = {}
    for path in args.input:
        supplied.update({item["id"]: item for item in json.loads(Path(path).read_text(encoding="utf-8"))["elements"]})
    if not args.input and not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            supplied = {item["id"]: item for item in json.loads(stdin_text).get("elements", [])}
    features = []
    for relation_id, (dong_id, name, data_area_id) in RELATIONS.items():
        relation = supplied.get(relation_id) or fetch_relation(relation_id)
        segments = []
        for member in relation["members"]:
            if member.get("type") != "way" or member.get("role") != "outer":
                continue
            segments.append([[point["lon"], point["lat"]] for point in member["geometry"]])
        rings = stitch(segments)
        geometry = {"type": "Polygon", "coordinates": rings} if len(rings) == 1 else {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}
        features.append({"type": "Feature", "properties": {"id": dong_id, "name": name, "data_area_id": data_area_id, "source": "OpenStreetMap contributors", "relation_id": relation_id}, "geometry": geometry})
        print(f"{name}: {len(rings)} ring(s)")
    OUTPUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(features)} features")


if __name__ == "__main__":
    main()
