"""
파일명 : optimization_service.py

역할
- 네이버 Maps API 결과를 프로젝트 공통 형식으로 가공
- 주소를 위도와 경도로 변환
- 두 좌표 사이의 거리와 이동시간을 계산
- 추후 알고리즘 담당자에게 전달할 데이터를 생성

현재 기능
- 주소 → 좌표 변환
- 출발지와 도착지 사이 차량 경로 조회

담당
- Backend / Data
"""

from typing import Any

from services.naver_map_service import geocode
from services.naver_map_service import get_directions


def convert_address_to_coordinate(
    address: str,
) -> dict[str, Any]:
    """
    배송지 주소를 위도와 경도로 변환한다.

    Parameters
    ----------
    address : str
        변환할 주소

    Returns
    -------
    dict[str, Any]
        프로젝트 내부 형식으로 가공한 좌표 정보
    """

    if not address or not address.strip():
        return {
            "success": False,
            "message": "주소를 입력해야 합니다.",
        }

    result = geocode(address.strip())

    addresses = result.get("addresses", [])

    if not addresses:
        return {
            "success": False,
            "message": "주소 검색 결과가 없습니다.",
        }

    location = addresses[0]

    return {
        "success": True,
        "address": address,
        "road_address": location.get("roadAddress"),
        "jibun_address": location.get("jibunAddress"),
        "latitude": float(location["y"]),
        "longitude": float(location["x"]),
    }


def calculate_route(
    start_longitude: float,
    start_latitude: float,
    goal_longitude: float,
    goal_latitude: float,
) -> dict[str, Any]:
    """
    출발지와 도착지 사이의 실제 차량 경로를 조회한다.

    Parameters
    ----------
    start_longitude : float
        출발지 경도

    start_latitude : float
        출발지 위도

    goal_longitude : float
        도착지 경도

    goal_latitude : float
        도착지 위도

    Returns
    -------
    dict[str, Any]
        거리, 예상 이동시간, 경로 좌표
    """

    result = get_directions(
        start_longitude=start_longitude,
        start_latitude=start_latitude,
        goal_longitude=goal_longitude,
        goal_latitude=goal_latitude,
    )

    if result.get("code") != 0:
        return {
            "success": False,
            "message": result.get(
                "message",
                "경로 조회에 실패했습니다.",
            ),
        }

    route_data = result.get("route", {})
    route_list = route_data.get("traoptimal", [])

    if not route_list:
        return {
            "success": False,
            "message": "조회된 차량 경로가 없습니다.",
        }

    first_route = route_list[0]
    summary = first_route.get("summary", {})

    distance_m = summary.get("distance", 0)
    duration_ms = summary.get("duration", 0)

    return {
        "success": True,
        "start": {
            "longitude": start_longitude,
            "latitude": start_latitude,
        },
        "goal": {
            "longitude": goal_longitude,
            "latitude": goal_latitude,
        },
        "distance_m": distance_m,
        "distance_km": round(distance_m / 1000, 2),
        "duration_ms": duration_ms,
        "duration_seconds": round(duration_ms / 1000),
        "duration_minutes": round(duration_ms / 60000, 1),
        "path": first_route.get("path", []),
    }