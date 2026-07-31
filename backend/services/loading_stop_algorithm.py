"""
배송지별 하역 정차 후보 추천 알고리즘.

1단계 목표
- 배송지별 후보지 분리
- 하드 제약 조건으로 부적합 후보 제거
- 적법성/도보 이동/도로 폭/혼잡도 점수 계산
- 배송지별 추천 정차지 반환
- 출발지가 있으면 배송 순서 계산

경로 최적화 방식
- 배송지 8개 이하: 모든 순서를 비교하는 완전탐색
- 배송지 9개 이상: 최근접 이웃 + 2-opt

주의
- 도보 거리 데이터가 없으면 직선거리로 임시 추정한다.
- 실제 도보 경로 및 차량 이동시간 행렬은 다음 단계에서
  외부 API 데이터로 교체한다.
"""

from __future__ import annotations

from itertools import permutations
from math import asin, cos, radians, sin, sqrt
import re
from typing import Any


WALKING_SPEED_M_PER_MINUTE = 80.0

# 완전탐색을 적용할 최대 배송지 개수
EXACT_SEARCH_MAX_DESTINATIONS = 8


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
    """
    Haversine 공식으로 두 좌표 사이의 직선거리(m)를 계산한다.
    """

    earth_radius_m = 6_371_000

    start_latitude_rad = radians(
        start_latitude
    )
    start_longitude_rad = radians(
        start_longitude
    )
    goal_latitude_rad = radians(
        goal_latitude
    )
    goal_longitude_rad = radians(
        goal_longitude
    )

    latitude_difference = (
        goal_latitude_rad
        - start_latitude_rad
    )

    longitude_difference = (
        goal_longitude_rad
        - start_longitude_rad
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


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    값을 최소값과 최대값 사이로 제한한다.
    """

    return max(
        minimum,
        min(value, maximum),
    )


def _merge_vehicle_profile(
    vehicle_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    기본 차량 정보와 사용자 입력 차량 정보를 병합한다.
    """

    merged = DEFAULT_VEHICLE_PROFILE.copy()

    if vehicle_profile:
        merged.update(
            {
                key: value
                for key, value
                in vehicle_profile.items()
                if value is not None
            }
        )

    return merged


# ============================================================
# [추가] 허용시간 문자열에서 최대 정차시간 추출
# ============================================================

def extract_max_stop_minutes(
    allowed_time_text: str,
) -> int:
    """
    허용시간 문자열에서 1회 최대 정차시간을 추출한다.

    처리 예:
    10:00 ~ 17:00 (1회, 15분이내)
        -> 15

    09:00~18:00(2시간이내)
        -> 120

    매일(24시간) 노상주차장설치
        -> 0

    반환값 0은 정차 제한시간을 알 수 없다는 의미다.
    """

    text = str(
        allowed_time_text or ""
    )

    text = text.replace(" ", "")

    minute_match = re.search(
        r"(\d+)분(?:이내|이하)?",
        text,
    )

    if minute_match:
        return int(
            minute_match.group(1)
        )

    hour_match = re.search(
        r"(\d+)시간(?:이내|이하)?",
        text,
    )

    if hour_match:
        return (
            int(hour_match.group(1))
            * 60
        )

    return 0


# ============================================================
# [추가] SHP 공간 검색 결과를 알고리즘 입력 형식으로 변환
# ============================================================

def convert_parking_segment_to_stop_candidate(
    segment: dict[str, Any],
    destination_id: str,
) -> dict[str, Any]:
    """
    parking_segment_service.py의 검색 결과를
    optimize_delivery_stop()에서 사용할 후보 형식으로 변환한다.

    parking_segment_service.py 결과 예:
    {
        "segment_id": "66",
        "segment_name": "중앙로",
        "stop_latitude": 36.329599,
        "stop_longitude": 127.428713,
        "distance_m": 596.32,
        "category": "택배소형화물차량",
        "is_time_allowed": True
    }

    변환 결과 예:
    {
        "id": "66",
        "name": "중앙로",
        "latitude": 36.329599,
        "longitude": 127.428713,
        "parking_available": True,
        "stop_allowed_at_request_time": True
    }
    """

    segment_id = str(
        segment.get(
            "segment_id",
            segment.get("code", ""),
        )
    ).strip()

    if not segment_id:
        raise ValueError(
            "정차 후보에 segment_id 또는 code가 없습니다."
        )

    if segment.get("stop_latitude") is None:
        raise ValueError(
            f"정차 후보 {segment_id}에 stop_latitude가 없습니다."
        )

    if segment.get("stop_longitude") is None:
        raise ValueError(
            f"정차 후보 {segment_id}에 stop_longitude가 없습니다."
        )

    category = str(
        segment.get("category", "")
    ).strip()

    usage_code = str(
        segment.get("usage_code", "")
    ).strip()

    is_time_allowed = segment.get(
        "is_time_allowed"
    )

    # 택배 또는 화물차 전용 허용구간
    if (
        "택배" in category
        or "화물" in category
    ):
        legality_score = 5.0

    # 용도 정보가 존재하는 일반 허용구간
    elif category:
        legality_score = 4.0

    # 용도 정보가 없는 구간
    else:
        legality_score = 3.0

    # 현재는 실제 혼잡도 API가 연결되지 않았으므로
    # 5점 만점 기준 중립값 3점 사용
    congestion_score = 3.0

    district = str(
        segment.get("district", "")
    ).strip()

    segment_name = str(
        segment.get(
            "segment_name",
            "이름 없는 허용구간",
        )
    ).strip()

    address_parts = [
        value
        for value in [
            district,
            segment_name,
        ]
        if value
    ]

    allowed_time = str(
        segment.get("allowed_time", "")
    )

    return {
        "id": segment_id,
        "name": (
            segment_name
            or "이름 없는 허용구간"
        ),
        "destination_id": destination_id,

        "latitude": float(
            segment["stop_latitude"]
        ),
        "longitude": float(
            segment["stop_longitude"]
        ),

        "address": " ".join(
            address_parts
        ),

        # parking_segment_service에서 계산한
        # 목적지와 정차구간 사이 최단 직선거리
        "walking_distance_m": float(
            segment.get(
                "distance_m",
                0.0,
            )
            or 0.0
        ),

        # 도보 시간은 알고리즘 내부에서
        # 분당 80m 기준으로 계산
        "walking_time_minutes": None,

        # SHP에 존재하는 구간은 기본 정차 후보로 판단
        "parking_available": True,

        # 명확히 True인 경우만 요청 시간대 허용으로 처리
        # False 또는 None이면 하드 제약에서 제외
        "stop_allowed_at_request_time": (
            is_time_allowed is True
        ),

        # 현재 데이터에 별도의 차량 진입 금지 정보가 없음
        "vehicle_entry_allowed": True,

        # 주정차 허용구간 SHP이므로 기본값 False
        "no_stopping_zone": False,

        # 필수 공간 정보가 존재하므로 sufficient
        "data_quality": "sufficient",

        "legality_score": legality_score,
        "congestion_score": congestion_score,

        # 실제 도로 폭 데이터가 연결되기 전까지 None
        "road_width_m": None,

        # 실제 높이 제한 데이터가 연결되기 전까지 None
        "height_limit_m": None,

        # 허용시간 문자열에서 정차 제한시간 추출
        "max_stop_minutes": (
            extract_max_stop_minutes(
                allowed_time
            )
        ),

        # 원본 SHP 정보
        "source_segment_id": (
            segment.get("segment_id")
        ),
        "source_code": segment.get("code"),
        "district": district,
        "segment_name": segment_name,
        "category": category,
        "usage_code": usage_code,
        "allowed_time": allowed_time,
        "allowed_date": segment.get(
            "allowed_date",
            "",
        ),
        "geometry_type": segment.get(
            "geometry_type",
            "",
        ),
        "time_check_reason": segment.get(
            "time_check_reason",
            "",
        ),

        # 목적지 원본 좌표
        "destination_latitude": segment.get(
            "destination_latitude"
        ),
        "destination_longitude": segment.get(
            "destination_longitude"
        ),
    }


# ============================================================
# [추가] 여러 배송지의 공간 검색 결과를 한 번에 변환
# ============================================================

def convert_parking_segments_to_stop_candidates(
    segments: list[dict[str, Any]],
    destination_id: str,
) -> list[dict[str, Any]]:
    """
    특정 배송지 주변의 SHP 검색 결과 전체를
    알고리즘 후보 형식으로 변환한다.
    """

    converted_candidates: list[
        dict[str, Any]
    ] = []

    for segment in segments:
        converted_candidate = (
            convert_parking_segment_to_stop_candidate(
                segment=segment,
                destination_id=destination_id,
            )
        )

        converted_candidates.append(
            converted_candidate
        )

    return converted_candidates


def _get_walking_metrics(
    candidate: dict[str, Any],
    destination: dict[str, Any],
) -> tuple[float, float, str]:
    """
    도보 거리, 도보 시간, 데이터 출처를 반환한다.
    """

    provided_distance = candidate.get(
        "walking_distance_m"
    )

    provided_time = candidate.get(
        "walking_time_minutes"
    )

    if provided_distance is not None:
        distance_m = max(
            float(provided_distance),
            0.0,
        )

        source = (
            "provided_walking_distance"
        )

    else:
        distance_m = (
            calculate_straight_distance(
                start_latitude=float(
                    candidate["latitude"]
                ),
                start_longitude=float(
                    candidate["longitude"]
                ),
                goal_latitude=float(
                    destination["latitude"]
                ),
                goal_longitude=float(
                    destination["longitude"]
                ),
            )
        )

        source = (
            "straight_distance_estimate"
        )

    if provided_time is not None:
        walking_time_minutes = max(
            float(provided_time),
            0.0,
        )

        if provided_distance is None:
            source = (
                "provided_walking_time"
            )
        else:
            source = (
                "provided_walking_distance_and_time"
            )

    else:
        walking_time_minutes = (
            distance_m
            / WALKING_SPEED_M_PER_MINUTE
        )

    return (
        distance_m,
        walking_time_minutes,
        source,
    )


def _get_hard_constraint_reasons(
    candidate: dict[str, Any],
    destination: dict[str, Any],
    vehicle_profile: dict[str, Any],
    max_walking_distance_m: float,
    walking_distance_m: float,
) -> list[str]:
    """
    후보지가 탈락해야 하는 하드 제약 사유를 반환한다.
    """

    reasons: list[str] = []

    if not candidate.get(
        "parking_available",
        True,
    ):
        reasons.append(
            "정차 불가능"
        )

    if candidate.get(
        "no_stopping_zone",
        False,
    ):
        reasons.append(
            "정차 절대 금지 구역"
        )

    if not candidate.get(
        "stop_allowed_at_request_time",
        True,
    ):
        reasons.append(
            "요청 시간대 정차 불가능"
        )

    if not candidate.get(
        "vehicle_entry_allowed",
        True,
    ):
        reasons.append(
            "차량 진입 금지"
        )

    data_quality = str(
        candidate.get(
            "data_quality",
            "sufficient",
        )
    ).lower()

    if data_quality in {
        "insufficient",
        "missing",
        "unreliable",
    }:
        reasons.append(
            "후보지 정보 부족"
        )

    vehicle_width_m = float(
        vehicle_profile["width_m"]
    )

    side_clearance_m = float(
        vehicle_profile[
            "side_clearance_m"
        ]
    )

    required_road_width_m = (
        vehicle_width_m
        + 2 * side_clearance_m
    )

    road_width_m = candidate.get(
        "road_width_m"
    )

    if (
        road_width_m is not None
        and float(road_width_m)
        < required_road_width_m
    ):
        reasons.append(
            "도로 폭 부족"
            f"({float(road_width_m):.1f}m"
            f" < {required_road_width_m:.1f}m)"
        )

    height_limit_m = candidate.get(
        "height_limit_m"
    )

    vehicle_height_m = float(
        vehicle_profile["height_m"]
    )

    if (
        height_limit_m is not None
        and float(height_limit_m) > 0
        and vehicle_height_m
        > float(height_limit_m)
    ):
        reasons.append(
            "차량 높이 제한 초과"
            f"({vehicle_height_m:.1f}m"
            f" > {float(height_limit_m):.1f}m)"
        )

    if (
        walking_distance_m
        > max_walking_distance_m
    ):
        reasons.append(
            "최대 도보 거리 초과"
            f"({walking_distance_m:.0f}m"
            f" > {max_walking_distance_m:.0f}m)"
        )

    max_stop_minutes = int(
        candidate.get(
            "max_stop_minutes",
            0,
        )
        or 0
    )

    required_stop_minutes = int(
        destination.get(
            "service_time_minutes",
            0,
        )
        or 0
    )

    if (
        max_stop_minutes > 0
        and required_stop_minutes > 0
        and max_stop_minutes
        < required_stop_minutes
    ):
        reasons.append(
            "정차 가능 시간 부족"
            f"({max_stop_minutes}분"
            f" < {required_stop_minutes}분)"
        )

    return reasons


def _calculate_road_width_score(
    candidate: dict[str, Any],
    vehicle_profile: dict[str, Any],
) -> float:
    """
    도로 폭 점수를 0~20점으로 계산한다.
    """

    road_width_m = candidate.get(
        "road_width_m"
    )

    if road_width_m is None:
        legacy_score = float(
            candidate.get(
                "road_width_score",
                0,
            )
            or 0
        )

        return round(
            _clamp(
                legacy_score,
                0.0,
                5.0,
            )
            * 4.0,
            2,
        )

    required_road_width_m = (
        float(
            vehicle_profile["width_m"]
        )
        + 2
        * float(
            vehicle_profile[
                "side_clearance_m"
            ]
        )
    )

    width_margin_m = (
        float(road_width_m)
        - required_road_width_m
    )

    # 하드 제약을 통과한 후보는 최소 10점에서 시작
    score = (
        10.0
        + (width_margin_m / 1.5)
        * 10.0
    )

    return round(
        _clamp(
            score,
            10.0,
            SCORE_WEIGHTS["road_width"],
        ),
        2,
    )


def calculate_destination_candidate_score(
    candidate: dict[str, Any],
    destination: dict[str, Any],
    vehicle_profile: dict[str, Any],
    max_walking_distance_m: float,
) -> dict[str, Any]:
    """
    하나의 배송지에 대한 정차 후보지의 적합도를 계산한다.
    """

    (
        walking_distance_m,
        walking_time_minutes,
        distance_source,
    ) = _get_walking_metrics(
        candidate=candidate,
        destination=destination,
    )

    rejected_reasons = (
        _get_hard_constraint_reasons(
            candidate=candidate,
            destination=destination,
            vehicle_profile=vehicle_profile,
            max_walking_distance_m=(
                max_walking_distance_m
            ),
            walking_distance_m=(
                walking_distance_m
            ),
        )
    )

    base_result: dict[str, Any] = {
        "candidate_id": candidate["id"],
        "candidate_name": candidate.get(
            "name",
            candidate["id"],
        ),
        "destination_id": destination["id"],
        "latitude": float(
            candidate["latitude"]
        ),
        "longitude": float(
            candidate["longitude"]
        ),
        "address": candidate.get(
            "address",
            "",
        ),
        "walking_distance_m": round(
            walking_distance_m,
            1,
        ),
        "walking_time_minutes": round(
            walking_time_minutes,
            1,
        ),
        "distance_source": distance_source,
        "max_stop_minutes": int(
            candidate.get(
                "max_stop_minutes",
                0,
            )
            or 0
        ),
        "road_width_m": candidate.get(
            "road_width_m"
        ),
        "height_limit_m": candidate.get(
            "height_limit_m"
        ),
        "eligible": not rejected_reasons,
        "rejected_reasons": (
            rejected_reasons
        ),

        # [추가] 원본 SHP 데이터 확인용
        "source_segment_id": candidate.get(
            "source_segment_id"
        ),
        "source_code": candidate.get(
            "source_code"
        ),
        "district": candidate.get(
            "district",
            "",
        ),
        "segment_name": candidate.get(
            "segment_name",
            "",
        ),
        "category": candidate.get(
            "category",
            "",
        ),
        "usage_code": candidate.get(
            "usage_code",
            "",
        ),
        "allowed_time": candidate.get(
            "allowed_time",
            "",
        ),
        "allowed_date": candidate.get(
            "allowed_date",
            "",
        ),
        "time_check_reason": candidate.get(
            "time_check_reason",
            "",
        ),
    }

    if rejected_reasons:
        return {
            **base_result,
            "score_breakdown": None,
            "total_score": None,
        }

    legality_score_raw = float(
        candidate.get(
            "legality_score",
            5,
        )
        or 0
    )

    legality_score = (
        _clamp(
            legality_score_raw,
            0.0,
            5.0,
        )
        / 5.0
        * SCORE_WEIGHTS["legality"]
    )

    walking_ratio = 1.0 - (
        walking_distance_m
        / max(
            max_walking_distance_m,
            1.0,
        )
    )

    walking_score = (
        _clamp(
            walking_ratio,
            0.0,
            1.0,
        )
        * SCORE_WEIGHTS["walking"]
    )

    road_width_score = (
        _calculate_road_width_score(
            candidate=candidate,
            vehicle_profile=vehicle_profile,
        )
    )

    congestion_score_raw = float(
        candidate.get(
            "congestion_score",
            3,
        )
        or 0
    )

    congestion_score = (
        _clamp(
            congestion_score_raw,
            0.0,
            5.0,
        )
        / 5.0
        * SCORE_WEIGHTS["congestion"]
    )

    score_breakdown = {
        "legality": round(
            legality_score,
            2,
        ),
        "walking": round(
            walking_score,
            2,
        ),
        "road_width": round(
            road_width_score,
            2,
        ),
        "congestion": round(
            congestion_score,
            2,
        ),
    }

    total_score = round(
        sum(
            score_breakdown.values()
        ),
        2,
    )

    return {
        **base_result,
        "score_breakdown": (
            score_breakdown
        ),
        "total_score": total_score,
    }


def _get_candidates_for_destination(
    destination_id: str,
    stop_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    특정 배송지에 연결된 정차 후보를 반환한다.
    """

    linked_candidates = [
        candidate
        for candidate in stop_candidates
        if candidate.get(
            "destination_id"
        )
        == destination_id
    ]

    if linked_candidates:
        return linked_candidates

    # destination_id가 없는 후보는
    # 모든 배송지가 공통으로 사용할 수 있는 후보로 간주
    return [
        candidate
        for candidate in stop_candidates
        if candidate.get(
            "destination_id"
        )
        in {
            None,
            "",
        }
    ]



# ============================================================
# [수정] 배송지 좌표 기준 경로 계산
# ============================================================

MAX_CANDIDATES_PER_DESTINATION = 5
VEHICLE_DISTANCE_SCORE_WEIGHT = 25.0
DEFAULT_MAX_VEHICLE_DISTANCE_M = 5000.0


def _destination_coordinate(
    result: dict[str, Any],
) -> tuple[float, float]:
    """
    배송 결과 객체에서 배송지 좌표를 반환한다.
    """

    return (
        float(result["destination_latitude"]),
        float(result["destination_longitude"]),
    )


def _calculate_destination_route_distance(
    start: dict[str, Any],
    ordered_results: list[dict[str, Any]],
) -> float:
    """
    출발지부터 배송지 좌표를 순서대로 방문할 때의
    전체 직선거리 합계를 계산한다.

    중요:
    초기 배송 순서는 정차지 좌표가 아니라
    배송지 좌표를 기준으로 계산한다.
    """

    current_latitude = float(start["latitude"])
    current_longitude = float(start["longitude"])
    total_distance_m = 0.0

    for result in ordered_results:
        destination_latitude, destination_longitude = (
            _destination_coordinate(result)
        )

        total_distance_m += calculate_straight_distance(
            start_latitude=current_latitude,
            start_longitude=current_longitude,
            goal_latitude=destination_latitude,
            goal_longitude=destination_longitude,
        )

        current_latitude = destination_latitude
        current_longitude = destination_longitude

    return total_distance_m


def _build_exact_destination_sequence(
    start: dict[str, Any],
    destination_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """
    배송지 8개 이하일 때 모든 배송 순서를 비교한다.
    정차지가 아니라 배송지 좌표를 기준으로 비교한다.
    """

    if not destination_results:
        return [], 0

    best_sequence: list[dict[str, Any]] | None = None
    best_distance_m = float("inf")
    evaluated_route_count = 0

    for sequence in permutations(destination_results):
        evaluated_route_count += 1
        sequence_list = list(sequence)

        distance_m = _calculate_destination_route_distance(
            start=start,
            ordered_results=sequence_list,
        )

        if distance_m < best_distance_m:
            best_distance_m = distance_m
            best_sequence = sequence_list

    return best_sequence or [], evaluated_route_count


def _build_nearest_neighbor_destination_sequence(
    start: dict[str, Any],
    destination_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    배송지 좌표를 기준으로 최근접 이웃 순서를 만든다.
    """

    remaining = destination_results.copy()
    current_latitude = float(start["latitude"])
    current_longitude = float(start["longitude"])
    ordered_results: list[dict[str, Any]] = []

    while remaining:
        next_result = min(
            remaining,
            key=lambda result: calculate_straight_distance(
                start_latitude=current_latitude,
                start_longitude=current_longitude,
                goal_latitude=float(
                    result["destination_latitude"]
                ),
                goal_longitude=float(
                    result["destination_longitude"]
                ),
            ),
        )

        ordered_results.append(next_result)
        current_latitude = float(
            next_result["destination_latitude"]
        )
        current_longitude = float(
            next_result["destination_longitude"]
        )
        remaining.remove(next_result)

    return ordered_results


def _apply_destination_two_opt(
    start: dict[str, Any],
    initial_sequence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    배송지 기준 최근접 이웃 경로에 2-opt를 적용한다.
    """

    if len(initial_sequence) < 3:
        return initial_sequence

    best_sequence = initial_sequence.copy()
    best_distance = _calculate_destination_route_distance(
        start=start,
        ordered_results=best_sequence,
    )

    improved = True

    while improved:
        improved = False

        for start_index in range(len(best_sequence) - 1):
            for end_index in range(
                start_index + 1,
                len(best_sequence),
            ):
                candidate_sequence = (
                    best_sequence[:start_index]
                    + list(
                        reversed(
                            best_sequence[
                                start_index:end_index + 1
                            ]
                        )
                    )
                    + best_sequence[end_index + 1:]
                )

                candidate_distance = (
                    _calculate_destination_route_distance(
                        start=start,
                        ordered_results=candidate_sequence,
                    )
                )

                if candidate_distance < best_distance:
                    best_sequence = candidate_sequence
                    best_distance = candidate_distance
                    improved = True
                    break

            if improved:
                break

    return best_sequence


def _format_destination_delivery_order(
    start: dict[str, Any] | None,
    ordered_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    배송지 방문 순서를 API 응답 형식으로 변환한다.

    초기 계획 단계에서는 정차지를 확정하지 않으므로
    stop_candidate_id는 기본적으로 None이다.
    """

    delivery_order: list[dict[str, Any]] = []

    if start is None:
        for order, result in enumerate(
            ordered_results,
            start=1,
        ):
            delivery_order.append(
                {
                    "order": order,
                    "destination_id": result["destination_id"],
                    "destination_name": result["destination_name"],
                    "destination_latitude": result[
                        "destination_latitude"
                    ],
                    "destination_longitude": result[
                        "destination_longitude"
                    ],
                    "stop_candidate_id": None,
                    "distance_from_previous_m": None,
                    "status": "pending",
                }
            )

        return delivery_order

    current_latitude = float(start["latitude"])
    current_longitude = float(start["longitude"])

    for order, result in enumerate(
        ordered_results,
        start=1,
    ):
        destination_latitude = float(
            result["destination_latitude"]
        )
        destination_longitude = float(
            result["destination_longitude"]
        )

        distance_m = calculate_straight_distance(
            start_latitude=current_latitude,
            start_longitude=current_longitude,
            goal_latitude=destination_latitude,
            goal_longitude=destination_longitude,
        )

        delivery_order.append(
            {
                "order": order,
                "destination_id": result["destination_id"],
                "destination_name": result["destination_name"],
                "destination_latitude": destination_latitude,
                "destination_longitude": destination_longitude,
                "stop_candidate_id": None,
                "distance_from_previous_m": round(
                    distance_m,
                    1,
                ),
                "status": "pending",
            }
        )

        current_latitude = destination_latitude
        current_longitude = destination_longitude

    return delivery_order


def _build_optimized_delivery_order(
    start: dict[str, Any] | None,
    destination_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    배송지 좌표를 기준으로 초기 배송 순서를 계산한다.

    출발지 없음:
        입력 순서 유지

    배송지 8개 이하:
        완전탐색

    배송지 9개 이상:
        최근접 이웃 + 2-opt
    """

    selectable_results = [
        result
        for result in destination_results
        if result.get("candidate_rankings")
    ]

    destination_count = len(selectable_results)

    if destination_count == 0:
        return [], {
            "algorithm": "none",
            "route_basis": "destination_coordinates",
            "is_optimal": True,
            "destination_count": 0,
            "evaluated_route_count": 0,
            "initial_distance_m": 0,
            "optimized_distance_m": 0,
            "improvement_distance_m": 0,
            "improvement_percent": 0,
        }

    if start is None:
        return (
            _format_destination_delivery_order(
                start=None,
                ordered_results=selectable_results,
            ),
            {
                "algorithm": "input_order",
                "route_basis": "destination_coordinates",
                "is_optimal": False,
                "destination_count": destination_count,
                "evaluated_route_count": 0,
                "initial_distance_m": None,
                "optimized_distance_m": None,
                "improvement_distance_m": None,
                "improvement_percent": None,
            },
        )

    initial_distance_m = (
        _calculate_destination_route_distance(
            start=start,
            ordered_results=selectable_results,
        )
    )

    if destination_count <= EXACT_SEARCH_MAX_DESTINATIONS:
        (
            optimized_sequence,
            evaluated_route_count,
        ) = _build_exact_destination_sequence(
            start=start,
            destination_results=selectable_results,
        )

        algorithm = "exact_permutation"
        is_optimal = True
    else:
        nearest_neighbor_sequence = (
            _build_nearest_neighbor_destination_sequence(
                start=start,
                destination_results=selectable_results,
            )
        )

        optimized_sequence = _apply_destination_two_opt(
            start=start,
            initial_sequence=nearest_neighbor_sequence,
        )

        evaluated_route_count = None
        algorithm = "nearest_neighbor_with_two_opt"
        is_optimal = False

    optimized_distance_m = (
        _calculate_destination_route_distance(
            start=start,
            ordered_results=optimized_sequence,
        )
    )

    improvement_distance_m = max(
        0.0,
        initial_distance_m - optimized_distance_m,
    )

    improvement_percent = (
        improvement_distance_m
        / initial_distance_m
        * 100
        if initial_distance_m > 0
        else 0.0
    )

    delivery_order = _format_destination_delivery_order(
        start=start,
        ordered_results=optimized_sequence,
    )

    return delivery_order, {
        "algorithm": algorithm,
        "route_basis": "destination_coordinates",
        "is_optimal": is_optimal,
        "destination_count": destination_count,
        "evaluated_route_count": evaluated_route_count,
        "initial_distance_m": round(
            initial_distance_m,
            1,
        ),
        "optimized_distance_m": round(
            optimized_distance_m,
            1,
        ),
        "improvement_distance_m": round(
            improvement_distance_m,
            1,
        ),
        "improvement_percent": round(
            improvement_percent,
            2,
        ),
    }


# ============================================================
# [추가] 현재 차량 위치를 반영한 다음 정차지 선택
# ============================================================

def select_next_stop(
    current_position: dict[str, Any],
    destination_result: dict[str, Any],
    max_vehicle_distance_m: float = (
        DEFAULT_MAX_VEHICLE_DISTANCE_M
    ),
) -> dict[str, Any]:
    """
    다음 배송지의 후보 중 실제로 이동할 정차지를 선택한다.

    후보의 기존 정적 점수에 다음을 추가한다.
    - 현재 차량 위치에서 후보 정차지까지의 직선거리
    - 가까울수록 높은 차량 이동 점수

    이 함수는 배송 완료 후 다음 정차지를 고를 때
    반복 호출할 수 있다.
    """

    if max_vehicle_distance_m <= 0:
        raise ValueError(
            "최대 차량 기준 거리는 0보다 커야 합니다."
        )

    candidates = destination_result.get(
        "candidate_rankings",
        [],
    )

    if not candidates:
        return {
            "success": False,
            "message": "선택 가능한 정차 후보가 없습니다.",
            "destination_id": destination_result.get(
                "destination_id"
            ),
            "selected_stop": None,
            "evaluated_candidates": [],
        }

    current_latitude = float(
        current_position["latitude"]
    )
    current_longitude = float(
        current_position["longitude"]
    )

    evaluated_candidates: list[
        dict[str, Any]
    ] = []

    for candidate in candidates:
        vehicle_distance_m = calculate_straight_distance(
            start_latitude=current_latitude,
            start_longitude=current_longitude,
            goal_latitude=float(candidate["latitude"]),
            goal_longitude=float(candidate["longitude"]),
        )

        vehicle_distance_ratio = 1.0 - (
            vehicle_distance_m
            / max(max_vehicle_distance_m, 1.0)
        )

        vehicle_distance_score = (
            _clamp(
                vehicle_distance_ratio,
                0.0,
                1.0,
            )
            * VEHICLE_DISTANCE_SCORE_WEIGHT
        )

        static_score = float(
            candidate.get("total_score", 0.0)
            or 0.0
        )

        dynamic_total_score = (
            static_score + vehicle_distance_score
        )

        evaluated_candidates.append(
            {
                **candidate,
                "vehicle_distance_m": round(
                    vehicle_distance_m,
                    1,
                ),
                "vehicle_distance_score": round(
                    vehicle_distance_score,
                    2,
                ),
                "static_total_score": round(
                    static_score,
                    2,
                ),
                "dynamic_total_score": round(
                    dynamic_total_score,
                    2,
                ),
            }
        )

    evaluated_candidates.sort(
        key=lambda candidate: (
            -float(candidate["dynamic_total_score"]),
            float(candidate["walking_distance_m"]),
            float(candidate["vehicle_distance_m"]),
            str(candidate["candidate_id"]),
        )
    )

    ranked_candidates = [
        {
            **candidate,
            "dynamic_rank": rank,
        }
        for rank, candidate in enumerate(
            evaluated_candidates,
            start=1,
        )
    ]

    selected_stop = ranked_candidates[0]

    return {
        "success": True,
        "destination_id": destination_result[
            "destination_id"
        ],
        "destination_name": destination_result[
            "destination_name"
        ],
        "selected_stop": selected_stop,
        "evaluated_candidates": ranked_candidates,
        "selection_method": (
            "기존 후보 점수 + 현재 차량 위치에서 "
            "후보까지의 거리 점수"
        ),
        "vehicle_distance_score_weight": (
            VEHICLE_DISTANCE_SCORE_WEIGHT
        ),
        "max_vehicle_distance_m": (
            max_vehicle_distance_m
        ),
    }


def select_next_stop_from_plan(
    plan_result: dict[str, Any],
    current_position: dict[str, Any],
    next_destination_id: str | None = None,
    completed_destination_ids: list[str] | None = None,
    max_vehicle_distance_m: float = (
        DEFAULT_MAX_VEHICLE_DISTANCE_M
    ),
) -> dict[str, Any]:
    """
    optimize_delivery_stop()이 만든 계획에서
    다음 배송지와 정차지를 선택한다.

    next_destination_id가 없으면 배송 순서에서
    완료되지 않은 첫 배송지를 자동 선택한다.
    """

    completed = set(completed_destination_ids or [])

    delivery_order = plan_result.get(
        "recommended_delivery_order",
        [],
    )

    if next_destination_id is None:
        next_order = next(
            (
                item
                for item in delivery_order
                if item["destination_id"]
                not in completed
            ),
            None,
        )

        if next_order is None:
            return {
                "success": False,
                "message": "남은 배송지가 없습니다.",
                "selected_stop": None,
            }

        next_destination_id = str(
            next_order["destination_id"]
        )

    destination_result = next(
        (
            result
            for result in plan_result.get(
                "destination_results",
                [],
            )
            if str(result["destination_id"])
            == str(next_destination_id)
        ),
        None,
    )

    if destination_result is None:
        return {
            "success": False,
            "message": (
                f"배송지 {next_destination_id}의 "
                "계획 데이터를 찾을 수 없습니다."
            ),
            "selected_stop": None,
        }

    return select_next_stop(
        current_position=current_position,
        destination_result=destination_result,
        max_vehicle_distance_m=max_vehicle_distance_m,
    )


# ============================================================
# [수정] 출발 전 전체 계획 생성
# ============================================================

def optimize_delivery_stop(
    destinations: list[dict[str, Any]],
    stop_candidates: list[dict[str, Any]],
    vehicle_profile: dict[str, Any] | None = None,
    max_walking_distance_m: float = 1500.0,
    start: dict[str, Any] | None = None,
    max_candidates_per_destination: int = (
        MAX_CANDIDATES_PER_DESTINATION
    ),
    select_first_stop: bool = True,
) -> dict[str, Any]:
    """
    출발 전에 전체 배송 계획을 생성한다.

    처리 순서
    1. 배송지별 정차 후보 평가
    2. 배송지별 상위 후보 보관
    3. 배송지 좌표 기준으로 방문 순서 계산
    4. 출발지가 있으면 첫 배송지 정차지만 확정

    이후 배송 완료 시 select_next_stop_from_plan()을 호출해
    실제 현재 위치를 기준으로 다음 정차지를 선택한다.
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

    if max_walking_distance_m <= 0:
        return {
            "success": False,
            "message": "최대 도보 거리는 0보다 커야 합니다.",
        }

    if max_candidates_per_destination <= 0:
        return {
            "success": False,
            "message": (
                "배송지별 최대 후보 수는 "
                "0보다 커야 합니다."
            ),
        }

    merged_vehicle_profile = _merge_vehicle_profile(
        vehicle_profile
    )

    destination_results: list[
        dict[str, Any]
    ] = []

    all_candidate_results: list[
        dict[str, Any]
    ] = []

    for destination in destinations:
        if "id" not in destination:
            raise ValueError(
                "배송지 데이터에 id가 없습니다."
            )

        if "latitude" not in destination:
            raise ValueError(
                f"배송지 {destination['id']}에 "
                "latitude가 없습니다."
            )

        if "longitude" not in destination:
            raise ValueError(
                f"배송지 {destination['id']}에 "
                "longitude가 없습니다."
            )

        candidates = _get_candidates_for_destination(
            destination_id=destination["id"],
            stop_candidates=stop_candidates,
        )

        evaluated_candidates = [
            calculate_destination_candidate_score(
                candidate=candidate,
                destination=destination,
                vehicle_profile=merged_vehicle_profile,
                max_walking_distance_m=(
                    max_walking_distance_m
                ),
            )
            for candidate in candidates
        ]

        all_candidate_results.extend(
            evaluated_candidates
        )

        eligible_candidates = [
            candidate
            for candidate in evaluated_candidates
            if candidate["eligible"]
        ]

        eligible_candidates.sort(
            key=lambda candidate: (
                -float(candidate["total_score"]),
                float(
                    candidate["walking_time_minutes"]
                ),
                str(candidate["candidate_id"]),
            )
        )

        # 후보가 지나치게 많으면 상위 N개만 보관한다.
        eligible_candidates = eligible_candidates[
            :max_candidates_per_destination
        ]

        candidate_rankings = [
            {
                **candidate,
                "rank": rank,
            }
            for rank, candidate in enumerate(
                eligible_candidates,
                start=1,
            )
        ]

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
                "destination_latitude": float(
                    destination["latitude"]
                ),
                "destination_longitude": float(
                    destination["longitude"]
                ),
                "service_time_minutes": int(
                    destination.get(
                        "service_time_minutes",
                        0,
                    )
                    or 0
                ),
                "status": (
                    "candidate_ready"
                    if candidate_rankings
                    else "no_eligible_candidate"
                ),

                # 초기 계획에서는 정차지를 확정하지 않는다.
                "recommended_stop": None,

                # 배송 시점에 다시 평가할 후보 목록
                "candidate_rankings": candidate_rankings,
                "rejected_candidates": rejected_candidates,
            }
        )

    (
        recommended_delivery_order,
        route_optimization,
    ) = _build_optimized_delivery_order(
        start=start,
        destination_results=destination_results,
    )

    unresolved_destination_ids = [
        result["destination_id"]
        for result in destination_results
        if not result["candidate_rankings"]
    ]

    first_stop_result: (
        dict[str, Any] | None
    ) = None

    if (
        select_first_stop
        and start is not None
        and recommended_delivery_order
    ):
        first_destination_id = (
            recommended_delivery_order[0][
                "destination_id"
            ]
        )

        first_stop_result = (
            select_next_stop_from_plan(
                plan_result={
                    "destination_results": (
                        destination_results
                    ),
                    "recommended_delivery_order": (
                        recommended_delivery_order
                    ),
                },
                current_position=start,
                next_destination_id=(
                    first_destination_id
                ),
            )
        )

        if first_stop_result.get("success"):
            selected_stop = first_stop_result[
                "selected_stop"
            ]

            destination_result = next(
                result
                for result in destination_results
                if result["destination_id"]
                == first_destination_id
            )

            destination_result[
                "recommended_stop"
            ] = selected_stop
            destination_result["status"] = (
                "next_stop_selected"
            )

            recommended_delivery_order[0][
                "stop_candidate_id"
            ] = selected_stop[
                "candidate_id"
            ]

            recommended_delivery_order[0][
                "selected_stop"
            ] = selected_stop

    selected_stops = []

    if (
        first_stop_result is not None
        and first_stop_result.get("success")
    ):
        selected_stops.append(
            {
                "destination_id": (
                    first_stop_result[
                        "destination_id"
                    ]
                ),
                "destination_name": (
                    first_stop_result[
                        "destination_name"
                    ]
                ),
                **first_stop_result[
                    "selected_stop"
                ],
            }
        )

    return {
        "success": True,

        # 배송지별 후보 목록
        "destination_results": destination_results,

        # 초기에는 첫 정차지만 들어간다.
        "selected_stops": selected_stops,
        "selected_stop": (
            selected_stops[0]
            if selected_stops
            else None
        ),
        "next_stop": (
            first_stop_result
            if first_stop_result is not None
            else None
        ),

        # 배송지 좌표 기준 전체 방문 순서
        "recommended_delivery_order": (
            recommended_delivery_order
        ),
        "route_optimization": route_optimization,

        "unresolved_destination_ids": (
            unresolved_destination_ids
        ),
        "total_destination_count": len(
            destinations
        ),
        "candidate_ready_destination_count": (
            len(destinations)
            - len(unresolved_destination_ids)
        ),
        "recommended_destination_count": (
            len(selected_stops)
        ),
        "candidate_results": all_candidate_results,
        "vehicle_profile": merged_vehicle_profile,
        "max_walking_distance_m": (
            max_walking_distance_m
        ),
        "max_candidates_per_destination": (
            max_candidates_per_destination
        ),
        "score_weights": SCORE_WEIGHTS,
        "calculation_method": {
            "planning": (
                "출발 전에 배송지별 후보를 평가하고 "
                "배송지 좌표 기준으로 전체 방문 순서를 계산"
            ),
            "stop_selection": (
                "각 배송 직전 현재 차량 위치와 "
                "후보의 정적 점수를 함께 반영"
            ),
            "delivery_order": (
                "배송지 8개 이하는 완전탐색, "
                "9개 이상은 최근접 이웃과 2-opt 적용"
                if start is not None
                else "출발지 미입력으로 입력 순서 유지"
            ),
            "walking_distance_fallback": (
                "도보 데이터가 없으면 "
                "직선거리와 분당 80m로 추정"
            ),
        },
    }


# ============================================================
# parking_segment_service 통합 실행 함수
# ============================================================

def recommend_stops_from_parking_segments(
    destinations: list[dict[str, Any]],
    parking_segments_by_destination: dict[
        str,
        list[dict[str, Any]],
    ],
    vehicle_profile: dict[str, Any] | None = None,
    max_walking_distance_m: float = 1500.0,
    start: dict[str, Any] | None = None,
    max_candidates_per_destination: int = (
        MAX_CANDIDATES_PER_DESTINATION
    ),
    select_first_stop: bool = True,
) -> dict[str, Any]:
    """
    배송지별 SHP 검색 결과를 후보 형식으로 변환한 뒤
    출발 전 배송 계획을 생성한다.
    """

    stop_candidates: list[
        dict[str, Any]
    ] = []

    for destination in destinations:
        destination_id = str(
            destination["id"]
        )

        parking_segments = (
            parking_segments_by_destination.get(
                destination_id,
                [],
            )
        )

        converted_candidates = (
            convert_parking_segments_to_stop_candidates(
                segments=parking_segments,
                destination_id=destination_id,
            )
        )

        stop_candidates.extend(converted_candidates)

    return optimize_delivery_stop(
        destinations=destinations,
        stop_candidates=stop_candidates,
        vehicle_profile=vehicle_profile,
        max_walking_distance_m=(
            max_walking_distance_m
        ),
        start=start,
        max_candidates_per_destination=(
            max_candidates_per_destination
        ),
        select_first_stop=select_first_stop,
    )


# ============================================================
# 단독 실행 테스트
# ============================================================

def run_test() -> None:
    """
    출발 전 계획 생성과 배송 완료 후 다음 정차지 선택을
    순서대로 테스트한다.
    """

    destinations = [
        {
            "id": "destination-1",
            "name": "대전역 배송지",
            "latitude": 36.332315,
            "longitude": 127.434447,
            "service_time_minutes": 10,
        },
        {
            "id": "destination-2",
            "name": "대전시청 배송지",
            "latitude": 36.350411,
            "longitude": 127.384548,
            "service_time_minutes": 10,
        },
    ]

    stop_candidates = [
        {
            "id": "S1",
            "destination_id": "destination-1",
            "name": "대전역 후보 1",
            "latitude": 36.329599,
            "longitude": 127.428713,
            "walking_distance_m": 596.3,
            "parking_available": True,
            "stop_allowed_at_request_time": True,
            "vehicle_entry_allowed": True,
            "no_stopping_zone": False,
            "data_quality": "sufficient",
            "legality_score": 5,
            "congestion_score": 3,
            "road_width_m": None,
            "height_limit_m": None,
            "max_stop_minutes": 15,
        },
        {
            "id": "S2",
            "destination_id": "destination-1",
            "name": "대전역 후보 2",
            "latitude": 36.325582,
            "longitude": 127.445386,
            "walking_distance_m": 1233.6,
            "parking_available": True,
            "stop_allowed_at_request_time": True,
            "vehicle_entry_allowed": True,
            "no_stopping_zone": False,
            "data_quality": "sufficient",
            "legality_score": 4,
            "congestion_score": 3,
            "road_width_m": None,
            "height_limit_m": None,
            "max_stop_minutes": 0,
        },
        {
            "id": "S3",
            "destination_id": "destination-2",
            "name": "시청 후보 1",
            "latitude": 36.351000,
            "longitude": 127.385000,
            "walking_distance_m": 80.0,
            "parking_available": True,
            "stop_allowed_at_request_time": True,
            "vehicle_entry_allowed": True,
            "no_stopping_zone": False,
            "data_quality": "sufficient",
            "legality_score": 5,
            "congestion_score": 4,
            "road_width_m": None,
            "height_limit_m": None,
            "max_stop_minutes": 20,
        },
    ]

    start = {
        "latitude": 36.360000,
        "longitude": 127.380000,
    }

    plan = optimize_delivery_stop(
        destinations=destinations,
        stop_candidates=stop_candidates,
        start=start,
        max_walking_distance_m=1500.0,
    )

    print("=" * 60)
    print("출발 전 배송 계획")
    print("=" * 60)
    print(
        "배송 순서:",
        plan["recommended_delivery_order"],
    )
    print(
        "첫 정차지:",
        plan["selected_stop"],
    )

    first_selected_stop = plan.get(
        "selected_stop"
    )

    if first_selected_stop is not None:
        completed_destination_id = (
            plan["recommended_delivery_order"][0][
                "destination_id"
            ]
        )

        next_result = select_next_stop_from_plan(
            plan_result=plan,
            current_position={
                "latitude": first_selected_stop[
                    "latitude"
                ],
                "longitude": first_selected_stop[
                    "longitude"
                ],
            },
            completed_destination_ids=[
                completed_destination_id
            ],
        )

        print("-" * 60)
        print("첫 배송 완료 후 다음 정차지")
        print(next_result)


if __name__ == "__main__":
    try:
        run_test()

    except Exception as error:
        print("[하역 정차 추천 알고리즘 실행 실패]")
        print(error)
        raise

