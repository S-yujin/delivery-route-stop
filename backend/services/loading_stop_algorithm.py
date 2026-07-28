"""배송지별 하역 정차 후보 추천 알고리즘.

1단계 목표
- 배송지별 후보지 분리
- 하드 제약 조건으로 부적합 후보 제거
- 적법성/도보 이동/도로 폭/혼잡도 점수 계산
- 배송지별 추천 정차지 반환
- 출발지가 있으면 최근접 이웃 방식으로 임시 배송 순서 계산

주의
- 도보 거리 데이터가 없으면 직선거리로 임시 추정한다.
- 실제 도보 경로 및 차량 이동시간 행렬은 다음 단계에서 외부 API 데이터로 교체한다.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

WALKING_SPEED_M_PER_MINUTE = 80.0

SCORE_WEIGHTS = {
    "legality": 30.0,
    "walking": 35.0,
    "road_width": 20.0,
    "congestion": 15.0,
}

DEFAULT_VEHICLE_PROFILE = {
    "vehicle_type": "small-truck",
    "width_m": 1.8,
    "height_m": 2.0,
    "side_clearance_m": 0.5,
}


def calculate_straight_distance(
    start_latitude: float,
    start_longitude: float,
    goal_latitude: float,
    goal_longitude: float,
) -> float:
    """Haversine 공식으로 두 좌표 사이 직선거리(m)를 계산한다."""
    earth_radius_m = 6_371_000

    start_latitude_rad = radians(start_latitude)
    start_longitude_rad = radians(start_longitude)
    goal_latitude_rad = radians(goal_latitude)
    goal_longitude_rad = radians(goal_longitude)

    latitude_difference = goal_latitude_rad - start_latitude_rad
    longitude_difference = goal_longitude_rad - start_longitude_rad

    haversine_value = (
        sin(latitude_difference / 2) ** 2
        + cos(start_latitude_rad)
        * cos(goal_latitude_rad)
        * sin(longitude_difference / 2) ** 2
    )
    central_angle = 2 * asin(sqrt(haversine_value))
    return earth_radius_m * central_angle


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _merge_vehicle_profile(
    vehicle_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = DEFAULT_VEHICLE_PROFILE.copy()
    if vehicle_profile:
        merged.update(
            {
                key: value
                for key, value in vehicle_profile.items()
                if value is not None
            }
        )
    return merged


def _get_walking_metrics(
    candidate: dict[str, Any],
    destination: dict[str, Any],
) -> tuple[float, float, str]:
    """도보 거리·시간과 데이터 출처를 반환한다."""
    provided_distance = candidate.get("walking_distance_m")
    provided_time = candidate.get("walking_time_minutes")

    if provided_distance is not None:
        distance_m = max(float(provided_distance), 0.0)
        source = "provided_walking_distance"
    else:
        distance_m = calculate_straight_distance(
            start_latitude=float(candidate["latitude"]),
            start_longitude=float(candidate["longitude"]),
            goal_latitude=float(destination["latitude"]),
            goal_longitude=float(destination["longitude"]),
        )
        source = "straight_distance_estimate"

    if provided_time is not None:
        walking_time_minutes = max(float(provided_time), 0.0)
        source = (
            "provided_walking_time"
            if provided_distance is None
            else "provided_walking_distance_and_time"
        )
    else:
        walking_time_minutes = distance_m / WALKING_SPEED_M_PER_MINUTE

    return distance_m, walking_time_minutes, source


def _get_hard_constraint_reasons(
    candidate: dict[str, Any],
    destination: dict[str, Any],
    vehicle_profile: dict[str, Any],
    max_walking_distance_m: float,
    walking_distance_m: float,
) -> list[str]:
    """후보지가 탈락해야 하는 하드 제약 사유를 반환한다."""
    reasons: list[str] = []

    if not candidate.get("parking_available", True):
        reasons.append("정차 불가능")

    if candidate.get("no_stopping_zone", False):
        reasons.append("정차 절대 금지 구역")

    if not candidate.get("stop_allowed_at_request_time", True):
        reasons.append("요청 시간대 정차 불가능")

    if not candidate.get("vehicle_entry_allowed", True):
        reasons.append("차량 진입 금지")

    if str(candidate.get("data_quality", "sufficient")).lower() in {
        "insufficient",
        "missing",
        "unreliable",
    }:
        reasons.append("후보지 정보 부족")

    vehicle_width_m = float(vehicle_profile["width_m"])
    side_clearance_m = float(vehicle_profile["side_clearance_m"])
    required_road_width_m = vehicle_width_m + 2 * side_clearance_m

    road_width_m = candidate.get("road_width_m")
    if road_width_m is not None and float(road_width_m) < required_road_width_m:
        reasons.append(
            "도로 폭 부족"
            f"({float(road_width_m):.1f}m < {required_road_width_m:.1f}m)"
        )

    height_limit_m = candidate.get("height_limit_m")
    vehicle_height_m = float(vehicle_profile["height_m"])
    if (
        height_limit_m is not None
        and float(height_limit_m) > 0
        and vehicle_height_m > float(height_limit_m)
    ):
        reasons.append(
            "차량 높이 제한 초과"
            f"({vehicle_height_m:.1f}m > {float(height_limit_m):.1f}m)"
        )

    if walking_distance_m > max_walking_distance_m:
        reasons.append(
            "최대 도보 거리 초과"
            f"({walking_distance_m:.0f}m > {max_walking_distance_m:.0f}m)"
        )

    max_stop_minutes = int(candidate.get("max_stop_minutes", 0) or 0)
    required_stop_minutes = int(
        destination.get("service_time_minutes", 0) or 0
    )
    if (
        max_stop_minutes > 0
        and required_stop_minutes > 0
        and max_stop_minutes < required_stop_minutes
    ):
        reasons.append(
            "정차 가능 시간 부족"
            f"({max_stop_minutes}분 < {required_stop_minutes}분)"
        )

    return reasons


def _calculate_road_width_score(
    candidate: dict[str, Any],
    vehicle_profile: dict[str, Any],
) -> float:
    """도로 폭 점수를 0~20점으로 계산한다."""
    road_width_m = candidate.get("road_width_m")

    if road_width_m is None:
        legacy_score = float(candidate.get("road_width_score", 0) or 0)
        return round(_clamp(legacy_score, 0.0, 5.0) * 4.0, 2)

    required_road_width_m = float(vehicle_profile["width_m"]) + (
        2 * float(vehicle_profile["side_clearance_m"])
    )
    width_margin_m = float(road_width_m) - required_road_width_m

    # 하드 제약을 통과한 후보는 최소 10점에서 시작한다.
    score = 10.0 + (width_margin_m / 1.5) * 10.0
    return round(_clamp(score, 10.0, SCORE_WEIGHTS["road_width"]), 2)


def calculate_destination_candidate_score(
    candidate: dict[str, Any],
    destination: dict[str, Any],
    vehicle_profile: dict[str, Any],
    max_walking_distance_m: float,
) -> dict[str, Any]:
    """하나의 배송지에 대한 정차 후보지의 적합도를 계산한다."""
    walking_distance_m, walking_time_minutes, distance_source = (
        _get_walking_metrics(candidate, destination)
    )

    rejected_reasons = _get_hard_constraint_reasons(
        candidate=candidate,
        destination=destination,
        vehicle_profile=vehicle_profile,
        max_walking_distance_m=max_walking_distance_m,
        walking_distance_m=walking_distance_m,
    )

    base_result: dict[str, Any] = {
        "candidate_id": candidate["id"],
        "candidate_name": candidate.get("name", candidate["id"]),
        "destination_id": destination["id"],
        "latitude": float(candidate["latitude"]),
        "longitude": float(candidate["longitude"]),
        "address": candidate.get("address", ""),
        "walking_distance_m": round(walking_distance_m, 1),
        "walking_time_minutes": round(walking_time_minutes, 1),
        "distance_source": distance_source,
        "max_stop_minutes": int(candidate.get("max_stop_minutes", 0) or 0),
        "road_width_m": candidate.get("road_width_m"),
        "height_limit_m": candidate.get("height_limit_m"),
        "eligible": not rejected_reasons,
        "rejected_reasons": rejected_reasons,
    }

    if rejected_reasons:
        return {
            **base_result,
            "score_breakdown": None,
            "total_score": None,
        }

    legality_score_raw = float(candidate.get("legality_score", 5) or 0)
    legality_score = (
        _clamp(legality_score_raw, 0.0, 5.0)
        / 5.0
        * SCORE_WEIGHTS["legality"]
    )

    walking_ratio = 1.0 - (
        walking_distance_m / max(max_walking_distance_m, 1.0)
    )
    walking_score = (
        _clamp(walking_ratio, 0.0, 1.0)
        * SCORE_WEIGHTS["walking"]
    )

    road_width_score = _calculate_road_width_score(
        candidate,
        vehicle_profile,
    )

    congestion_score_raw = float(candidate.get("congestion_score", 3) or 0)
    congestion_score = (
        _clamp(congestion_score_raw, 0.0, 5.0)
        / 5.0
        * SCORE_WEIGHTS["congestion"]
    )

    score_breakdown = {
        "legality": round(legality_score, 2),
        "walking": round(walking_score, 2),
        "road_width": round(road_width_score, 2),
        "congestion": round(congestion_score, 2),
    }
    total_score = round(sum(score_breakdown.values()), 2)

    return {
        **base_result,
        "score_breakdown": score_breakdown,
        "total_score": total_score,
    }


def _get_candidates_for_destination(
    destination_id: str,
    stop_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    linked_candidates = [
        candidate
        for candidate in stop_candidates
        if candidate.get("destination_id") == destination_id
    ]
    if linked_candidates:
        return linked_candidates

    # destination_id가 없는 후보는 여러 배송지가 공통으로 사용할 수 있는
    # 후보로 간주하여 기존 요청 형식과의 호환성을 유지한다.
    return [
        candidate
        for candidate in stop_candidates
        if candidate.get("destination_id") in {None, ""}
    ]


def _build_nearest_neighbor_order(
    start: dict[str, Any] | None,
    destination_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """추천 정차지 좌표를 기준으로 최근접 이웃 배송 순서를 만든다."""
    selectable_results = [
        result
        for result in destination_results
        if result.get("recommended_stop") is not None
    ]
    if not selectable_results:
        return []

    if start is None:
        return [
            {
                "order": index,
                "destination_id": result["destination_id"],
                "destination_name": result["destination_name"],
                "stop_candidate_id": result["recommended_stop"][
                    "candidate_id"
                ],
                "distance_from_previous_m": None,
            }
            for index, result in enumerate(selectable_results, start=1)
        ]

    current_latitude = float(start["latitude"])
    current_longitude = float(start["longitude"])
    remaining = selectable_results.copy()
    ordered: list[dict[str, Any]] = []

    while remaining:
        next_result = min(
            remaining,
            key=lambda result: calculate_straight_distance(
                current_latitude,
                current_longitude,
                float(result["recommended_stop"]["latitude"]),
                float(result["recommended_stop"]["longitude"]),
            ),
        )
        next_stop = next_result["recommended_stop"]
        distance_m = calculate_straight_distance(
            current_latitude,
            current_longitude,
            float(next_stop["latitude"]),
            float(next_stop["longitude"]),
        )

        ordered.append(
            {
                "order": len(ordered) + 1,
                "destination_id": next_result["destination_id"],
                "destination_name": next_result["destination_name"],
                "stop_candidate_id": next_stop["candidate_id"],
                "distance_from_previous_m": round(distance_m, 1),
            }
        )
        current_latitude = float(next_stop["latitude"])
        current_longitude = float(next_stop["longitude"])
        remaining.remove(next_result)

    return ordered


def optimize_delivery_stop(
    destinations: list[dict[str, Any]],
    stop_candidates: list[dict[str, Any]],
    vehicle_profile: dict[str, Any] | None = None,
    max_walking_distance_m: float = 300.0,
    start: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """배송지별 정차 후보지를 평가하고 추천 결과를 반환한다."""
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

    if max_walking_distance_m <= 0:
        return {
            "success": False,
            "message": "최대 도보 거리는 0보다 커야 합니다.",
        }

    merged_vehicle_profile = _merge_vehicle_profile(vehicle_profile)
    destination_results: list[dict[str, Any]] = []
    all_candidate_results: list[dict[str, Any]] = []

    for destination in destinations:
        candidates = _get_candidates_for_destination(
            destination_id=destination["id"],
            stop_candidates=stop_candidates,
        )

        evaluated_candidates = [
            calculate_destination_candidate_score(
                candidate=candidate,
                destination=destination,
                vehicle_profile=merged_vehicle_profile,
                max_walking_distance_m=max_walking_distance_m,
            )
            for candidate in candidates
        ]
        all_candidate_results.extend(evaluated_candidates)

        eligible_candidates = [
            candidate
            for candidate in evaluated_candidates
            if candidate["eligible"]
        ]
        eligible_candidates.sort(
            key=lambda candidate: (
                -float(candidate["total_score"]),
                float(candidate["walking_time_minutes"]),
                candidate["candidate_id"],
            )
        )

        candidate_rankings: list[dict[str, Any]] = []
        for rank, candidate in enumerate(eligible_candidates, start=1):
            candidate_rankings.append({**candidate, "rank": rank})

        rejected_candidates = [
            candidate
            for candidate in evaluated_candidates
            if not candidate["eligible"]
        ]

        destination_results.append(
            {
                "destination_id": destination["id"],
                "destination_name": destination.get(
                    "name",
                    destination["id"],
                ),
                "status": (
                    "recommended"
                    if candidate_rankings
                    else "no_eligible_candidate"
                ),
                "recommended_stop": (
                    candidate_rankings[0]
                    if candidate_rankings
                    else None
                ),
                "candidate_rankings": candidate_rankings,
                "rejected_candidates": rejected_candidates,
            }
        )

    selected_stops = [
        {
            "destination_id": result["destination_id"],
            "destination_name": result["destination_name"],
            **result["recommended_stop"],
        }
        for result in destination_results
        if result["recommended_stop"] is not None
    ]

    recommended_delivery_order = _build_nearest_neighbor_order(
        start=start,
        destination_results=destination_results,
    )

    unresolved_destination_ids = [
        result["destination_id"]
        for result in destination_results
        if result["recommended_stop"] is None
    ]

    return {
        "success": True,
        "destination_results": destination_results,
        "selected_stops": selected_stops,
        # 기존 단일 후보 응답을 참조하는 코드가 있을 경우를 위한 호환 필드
        "selected_stop": selected_stops[0] if selected_stops else None,
        "recommended_delivery_order": recommended_delivery_order,
        "unresolved_destination_ids": unresolved_destination_ids,
        "total_destination_count": len(destinations),
        "recommended_destination_count": len(selected_stops),
        "candidate_results": all_candidate_results,
        "vehicle_profile": merged_vehicle_profile,
        "max_walking_distance_m": max_walking_distance_m,
        "score_weights": SCORE_WEIGHTS,
        "calculation_method": {
            "stop_selection": (
                "하드 제약 필터링 후 적법성·도보 이동·도로 폭·"
                "혼잡도 가중합"
            ),
            "delivery_order": (
                "추천 정차지 직선거리 기반 최근접 이웃"
                if start is not None
                else "출발지 미입력으로 배송지 입력 순서 유지"
            ),
            "walking_distance_fallback": (
                "도보 데이터가 없으면 직선거리와 분당 80m로 추정"
            ),
        },
    }
