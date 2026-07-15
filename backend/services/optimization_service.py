"""
파일명 : optimization_service.py

역할
- 네이버 Maps API 결과를 프로젝트 공통 형식으로 가공
- 주소를 위도와 경도로 변환
- 두 좌표 사이의 거리와 이동시간을 계산
- 정차 후보지와 배송지 사이의 직선거리를 계산
- 배송지와 가까운 정차 후보지를 추천
- 추후 알고리즘 담당자에게 전달할 데이터를 생성

현재 기능
- 주소 → 좌표 변환
- 출발지와 도착지 사이 차량 경로 조회
- 두 좌표 사이 직선거리 계산
- 정차 후보지별 거리 점수 계산
- 최적 정차 후보지 추천

담당
- Backend / Data
"""

from math import asin
from math import cos
from math import radians
from math import sin
from math import sqrt
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


def calculate_straight_distance(
    start_latitude: float,
    start_longitude: float,
    goal_latitude: float,
    goal_longitude: float,
) -> float:
    """
    두 좌표 사이의 직선거리를 Haversine 공식으로 계산한다.

    네이버 Directions API를 호출하지 않기 때문에
    여러 정차 후보지를 빠르게 비교할 때 사용한다.

    Parameters
    ----------
    start_latitude : float
        출발지 위도

    start_longitude : float
        출발지 경도

    goal_latitude : float
        도착지 위도

    goal_longitude : float
        도착지 경도

    Returns
    -------
    float
        두 좌표 사이의 거리(m)
    """

    earth_radius_m = 6_371_000

    start_latitude_rad = radians(start_latitude)
    start_longitude_rad = radians(start_longitude)
    goal_latitude_rad = radians(goal_latitude)
    goal_longitude_rad = radians(goal_longitude)

    latitude_difference = (
        goal_latitude_rad - start_latitude_rad
    )
    longitude_difference = (
        goal_longitude_rad - start_longitude_rad
    )

    haversine_value = (
        sin(latitude_difference / 2) ** 2
        + cos(start_latitude_rad)
        * cos(goal_latitude_rad)
        * sin(longitude_difference / 2) ** 2
    )

    central_angle = 2 * asin(
        sqrt(haversine_value)
    )

    return earth_radius_m * central_angle


def calculate_candidate_score(
    candidate: dict[str, Any],
    destinations: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    하나의 정차 후보지와 모든 배송지 사이의 거리를 계산한다.

    배송 물량이 많은 배송지는 더 중요하다고 판단하여
    delivery_count 값을 거리 가중치로 사용한다.

    Parameters
    ----------
    candidate : dict[str, Any]
        평가할 정차 후보지

    destinations : list[dict[str, Any]]
        배송지 목록

    Returns
    -------
    dict[str, Any]
        후보지의 총거리, 가중거리, 배송지별 거리
    """

    total_distance_m = 0.0
    weighted_distance_m = 0.0
    destination_distances: list[dict[str, Any]] = []

    candidate_latitude = float(candidate["latitude"])
    candidate_longitude = float(candidate["longitude"])

    for destination in destinations:
        destination_latitude = float(
            destination["latitude"]
        )
        destination_longitude = float(
            destination["longitude"]
        )

        distance_m = calculate_straight_distance(
            start_latitude=candidate_latitude,
            start_longitude=candidate_longitude,
            goal_latitude=destination_latitude,
            goal_longitude=destination_longitude,
        )

        delivery_count = int(
            destination.get("delivery_count", 1)
        )

        if delivery_count < 1:
            delivery_count = 1

        total_distance_m += distance_m
        weighted_distance_m += (
            distance_m * delivery_count
        )

        destination_distances.append(
            {
                "destination_id": destination["id"],
                "destination_name": destination.get(
                    "name",
                    destination["id"],
                ),
                "distance_m": round(distance_m, 1),
                "distance_km": round(
                    distance_m / 1000,
                    3,
                ),
                "delivery_count": delivery_count,
                "service_time_minutes": destination.get(
                    "service_time_minutes",
                    0,
                ),
            }
        )

    destination_distances.sort(
        key=lambda item: item["distance_m"]
    )

    return {
        "candidate_id": candidate["id"],
        "candidate_name": candidate.get(
            "name",
            candidate["id"],
        ),
        "total_distance_m": round(
            total_distance_m,
            1,
        ),
        "total_distance_km": round(
            total_distance_m / 1000,
            3,
        ),
        "weighted_distance_m": round(
            weighted_distance_m,
            1,
        ),
        "destination_distances": destination_distances,
    }


def optimize_delivery_stop(
    destinations: list[dict[str, Any]],
    stop_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    배송지 목록과 정차 후보지 목록을 비교하여
    가장 적합한 정차 후보지를 선택한다.

    현재 임시 추천 기준
    1. 주차가 불가능한 후보지는 제외한다.
    2. 후보지와 배송지 사이의 직선거리를 계산한다.
    3. 배송 물량을 거리 가중치로 반영한다.
    4. 가중거리 합이 가장 작은 후보지를 선택한다.
    5. 가중거리가 같으면 안전성과 도로 폭 점수를 비교한다.
    6. 선택된 후보지에서 가까운 배송지 순서를 반환한다.

    Parameters
    ----------
    destinations : list[dict[str, Any]]
        배송지 목록

    stop_candidates : list[dict[str, Any]]
        정차 후보지 목록

    Returns
    -------
    dict[str, Any]
        추천 정차 후보지와 배송 순서
    """

    if not destinations:
        return {
            "success": False,
            "message": "배송지 목록이 비어 있습니다.",
        }

    if not stop_candidates:
        return {
            "success": False,
            "message": "정차 후보지 목록이 비어 있습니다.",
        }

    available_candidates = [
        candidate
        for candidate in stop_candidates
        if candidate.get(
            "parking_available",
            True,
        )
    ]

    if not available_candidates:
        return {
            "success": False,
            "message": "정차 가능한 후보지가 없습니다.",
        }

    candidate_results: list[dict[str, Any]] = []

    for candidate in available_candidates:
        candidate_result = calculate_candidate_score(
            candidate=candidate,
            destinations=destinations,
        )

        candidate_result["parking_available"] = (
            candidate.get(
                "parking_available",
                True,
            )
        )
        candidate_result["max_stop_minutes"] = (
            candidate.get(
                "max_stop_minutes",
                0,
            )
        )
        candidate_result["road_width_score"] = (
            candidate.get(
                "road_width_score",
                0,
            )
        )
        candidate_result["safety_score"] = (
            candidate.get(
                "safety_score",
                0,
            )
        )

        candidate_results.append(candidate_result)

    candidate_results.sort(
        key=lambda result: (
            result["weighted_distance_m"],
            -result["safety_score"],
            -result["road_width_score"],
        )
    )

    best_result = candidate_results[0]

    selected_candidate = next(
        candidate
        for candidate in available_candidates
        if candidate["id"]
        == best_result["candidate_id"]
    )

    recommended_delivery_order = [
        {
            "order": index,
            "destination_id": item[
                "destination_id"
            ],
            "destination_name": item[
                "destination_name"
            ],
            "distance_m": item["distance_m"],
            "distance_km": item["distance_km"],
            "delivery_count": item[
                "delivery_count"
            ],
        }
        for index, item in enumerate(
            best_result["destination_distances"],
            start=1,
        )
    ]

    total_delivery_count = sum(
        int(destination.get("delivery_count", 1))
        for destination in destinations
    )

    total_service_time_minutes = sum(
        int(
            destination.get(
                "service_time_minutes",
                0,
            )
        )
        for destination in destinations
    )

    return {
        "success": True,
        "selected_stop": {
            "id": selected_candidate["id"],
            "name": selected_candidate.get(
                "name",
                selected_candidate["id"],
            ),
            "latitude": float(
                selected_candidate["latitude"]
            ),
            "longitude": float(
                selected_candidate["longitude"]
            ),
            "parking_available": (
                selected_candidate.get(
                    "parking_available",
                    True,
                )
            ),
            "max_stop_minutes": (
                selected_candidate.get(
                    "max_stop_minutes",
                    0,
                )
            ),
            "road_width_score": (
                selected_candidate.get(
                    "road_width_score",
                    0,
                )
            ),
            "safety_score": (
                selected_candidate.get(
                    "safety_score",
                    0,
                )
            ),
        },
        "recommended_delivery_order": (
            recommended_delivery_order
        ),
        "total_destination_count": len(
            destinations
        ),
        "total_delivery_count": total_delivery_count,
        "total_service_time_minutes": (
            total_service_time_minutes
        ),
        "total_distance_m": best_result[
            "total_distance_m"
        ],
        "total_distance_km": best_result[
            "total_distance_km"
        ],
        "weighted_distance_m": best_result[
            "weighted_distance_m"
        ],
        "candidate_results": candidate_results,
        "calculation_method": (
            "배송 물량 가중치를 적용한 "
            "직선거리 기반 임시 추천"
        ),
    }