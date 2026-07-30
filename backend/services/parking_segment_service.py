from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time
import re
from typing import Any

import geopandas as gpd
from geopandas import GeoDataFrame
from shapely.geometry import Point
from shapely.ops import nearest_points

from backend.services.spatial_data_loader import (
    load_parking_allowed_geodataframe,
)


# 거리 계산용 좌표계
DISTANCE_CRS = "EPSG:5179"

# 위도·경도 반환용 좌표계
WGS84_CRS = "EPSG:4326"


@dataclass
class ParkingSegmentCandidate:
    segment_id: str
    district: str
    segment_name: str
    code: str
    category: str
    usage_code: str
    allowed_time: str
    allowed_date: str

    stop_latitude: float
    stop_longitude: float

    destination_latitude: float
    destination_longitude: float

    distance_m: float
    geometry_type: str

    is_time_allowed: bool | None
    time_check_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in {
        "",
        "nan",
        "none",
        "null",
        "nat",
    }:
        return ""

    return text


def normalize_time_text(value: str) -> str:
    """
    여러 종류의 시간 범위 기호를 ~ 기호로 통일한다.

    예:
    09:00∼18:00
    09:00～18:00
    09:00-18:00
    """

    text = clean_text(value)

    text = text.replace("∼", "~")
    text = text.replace("～", "~")
    text = text.replace("—", "~")
    text = text.replace("–", "~")

    return text


def get_row_value(
    row: Any,
    candidate_columns: list[str],
) -> str:
    for column_name in candidate_columns:
        if column_name in row.index:
            value = clean_text(row[column_name])

            if value:
                return value

    return ""


def validate_coordinate(
    latitude: float,
    longitude: float,
) -> None:
    if not -90 <= latitude <= 90:
        raise ValueError(
            f"위도 범위가 올바르지 않습니다: {latitude}"
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            f"경도 범위가 올바르지 않습니다: {longitude}"
        )


def create_destination_geodataframe(
    latitude: float,
    longitude: float,
) -> GeoDataFrame:
    validate_coordinate(
        latitude=latitude,
        longitude=longitude,
    )

    destination_point = Point(
        longitude,
        latitude,
    )

    return gpd.GeoDataFrame(
        [
            {
                "destination_latitude": latitude,
                "destination_longitude": longitude,
            }
        ],
        geometry=[destination_point],
        crs=WGS84_CRS,
    )


def parse_time_value(value: str) -> time | None:
    """
    문자열에서 HH:MM 형식의 시간을 추출한다.
    """

    matched = re.search(
        r"(\d{1,2})\s*:\s*(\d{2})",
        value,
    )

    if matched is None:
        return None

    hour = int(matched.group(1))
    minute = int(matched.group(2))

    if not 0 <= hour <= 23:
        return None

    if not 0 <= minute <= 59:
        return None

    return time(
        hour=hour,
        minute=minute,
    )


def parse_allowed_time_range(
    allowed_time_text: str,
) -> tuple[time, time] | None:
    """
    문자열에서 첫 번째 시작 시간과 종료 시간을 추출한다.

    처리 예:
    11:30∼14:00
    09:00~18:00
    20:00∼07:00
    """

    cleaned = normalize_time_text(
        allowed_time_text
    )

    if not cleaned:
        return None

    matched_times = re.findall(
        r"\d{1,2}\s*:\s*\d{2}",
        cleaned,
    )

    if len(matched_times) < 2:
        return None

    start_time = parse_time_value(
        matched_times[0]
    )

    end_time = parse_time_value(
        matched_times[1]
    )

    if start_time is None or end_time is None:
        return None

    return start_time, end_time


def is_time_within_range(
    target_time: time,
    start_time: time,
    end_time: time,
) -> bool:
    """
    일반 시간 범위와 자정을 넘는 시간 범위를 처리한다.

    일반:
    09:00~18:00

    자정 통과:
    20:00~07:00
    """

    if start_time <= end_time:
        return start_time <= target_time <= end_time

    return (
        target_time >= start_time
        or target_time <= end_time
    )


def contains_24_hours(text: str) -> bool:
    """
    문자열에 24시간 허용 표현이 있는지 확인한다.
    """

    normalized = (
        normalize_time_text(text)
        .replace(" ", "")
    )

    patterns = [
        "24시간",
        "24시",
        "00:00~24:00",
        "0:00~24:00",
        "00:00~00:00",
    ]

    return any(
        pattern in normalized
        for pattern in patterns
    )


def has_day_condition(text: str) -> bool:
    normalized = clean_text(text).replace(" ", "")

    return any(
        keyword in normalized
        for keyword in [
            "평일",
            "주말",
            "토요일",
            "일요일",
            "공휴일",
        ]
    )


def check_time_range(
    request_datetime: datetime,
    parsed_range: tuple[time, time] | None,
    condition_name: str,
) -> tuple[bool | None, str]:
    """
    파싱된 시간 범위를 기준 일시와 비교한다.
    """

    if parsed_range is None:
        return (
            None,
            f"{condition_name} 허용시간 범위를 해석할 수 없습니다.",
        )

    start_time, end_time = parsed_range

    is_allowed = is_time_within_range(
        target_time=request_datetime.time(),
        start_time=start_time,
        end_time=end_time,
    )

    start_text = start_time.strftime("%H:%M")
    end_text = end_time.strftime("%H:%M")

    if is_allowed:
        return (
            True,
            (
                f"{condition_name}이며 현재 시간이 허용시간 "
                f"{start_text}~{end_text} 범위에 포함됩니다."
            ),
        )

    return (
        False,
        (
            f"{condition_name}이지만 현재 시간이 허용시간 "
            f"{start_text}~{end_text} 범위에 포함되지 않습니다."
        ),
    )


def check_allowed_time_detail(
    allowed_time_text: str,
    request_datetime: datetime | None,
    is_public_holiday: bool | None = None,
) -> tuple[bool | None, str]:
    """
    허용시간, 요일, 공휴일 조건을 함께 판정한다.

    처리 예:
    - 매일 24시간
    - 평일 09:00~18:00
    - 주말 10:00~17:00
    - 토요일 09:00~13:00
    - 20:00~07:00
    - 09:00~18:00 (평일) 공휴일 24시간

    반환값:
    True:
        현재 일시에 이용 가능

    False:
        현재 일시에 이용 불가능

    None:
        현재 데이터로 정확히 판정할 수 없음
    """

    cleaned = normalize_time_text(
        allowed_time_text
    )

    if not cleaned:
        return (
            None,
            "허용시간 정보가 없습니다.",
        )

    if request_datetime is None:
        return (
            None,
            "시간 판별 기준 일시가 없습니다.",
        )

    compact_text = cleaned.replace(" ", "")

    weekday_number = request_datetime.weekday()

    is_current_weekday = weekday_number <= 4
    is_current_weekend = weekday_number >= 5
    is_current_saturday = weekday_number == 5
    is_current_sunday = weekday_number == 6

    has_weekday_text = "평일" in compact_text
    has_weekend_text = "주말" in compact_text
    has_saturday_text = "토요일" in compact_text
    has_sunday_text = "일요일" in compact_text
    has_holiday_text = "공휴일" in compact_text

    has_24_hour_text = contains_24_hours(
        cleaned
    )

    parsed_range = parse_allowed_time_range(
        cleaned
    )

    # --------------------------------------------------
    # 1. 공휴일 조건 처리
    # --------------------------------------------------

    if is_public_holiday is True:
        if has_holiday_text:
            if has_24_hour_text:
                return (
                    True,
                    "공휴일 24시간 허용구간입니다.",
                )

            return check_time_range(
                request_datetime=request_datetime,
                parsed_range=parsed_range,
                condition_name="공휴일",
            )

        if has_weekday_text:
            return (
                False,
                "공휴일은 평일 허용 조건에 포함되지 않습니다.",
            )

    # 공휴일 전용 구간인데 오늘이 공휴일이 아님
    if is_public_holiday is False:
        holiday_only = (
            has_holiday_text
            and not has_weekday_text
            and not has_weekend_text
            and not has_saturday_text
            and not has_sunday_text
        )

        if holiday_only:
            return (
                False,
                "공휴일 전용 허용구간입니다.",
            )

    # 공휴일 여부를 모르는데 공휴일 조건만 있는 경우
    if is_public_holiday is None:
        holiday_only = (
            has_holiday_text
            and not has_weekday_text
            and not has_weekend_text
            and not has_saturday_text
            and not has_sunday_text
        )

        if holiday_only:
            return (
                None,
                "공휴일 여부 정보가 없어 판별할 수 없습니다.",
            )

    # --------------------------------------------------
    # 2. 매일 또는 상시 24시간 처리
    # --------------------------------------------------

    is_everyday_24_hours = (
        has_24_hour_text
        and (
            "매일" in compact_text
            or "상시" in compact_text
            or "종일" in compact_text
            or "노상주차장설치" in compact_text
        )
        and not has_weekday_text
        and not has_weekend_text
        and not has_saturday_text
        and not has_sunday_text
        and not has_holiday_text
    )

    if is_everyday_24_hours:
        return (
            True,
            "매일 24시간 허용구간입니다.",
        )

    # --------------------------------------------------
    # 3. 평일 + 공휴일 조건이 함께 있는 경우
    # --------------------------------------------------

    if has_weekday_text and has_holiday_text:
        if is_public_holiday is True:
            if has_24_hour_text:
                return (
                    True,
                    "공휴일 24시간 허용구간입니다.",
                )

            return check_time_range(
                request_datetime=request_datetime,
                parsed_range=parsed_range,
                condition_name="공휴일",
            )

        if not is_current_weekday:
            return (
                False,
                "현재 날짜는 평일이 아닙니다.",
            )

        return check_time_range(
            request_datetime=request_datetime,
            parsed_range=parsed_range,
            condition_name="평일",
        )

    # --------------------------------------------------
    # 4. 평일 조건 처리
    # --------------------------------------------------

    if has_weekday_text:
        if not is_current_weekday:
            return (
                False,
                "현재 날짜는 평일이 아닙니다.",
            )

        if is_public_holiday is True:
            return (
                False,
                "공휴일은 평일 허용 조건에 포함되지 않습니다.",
            )

        if has_24_hour_text:
            return (
                True,
                "평일 24시간 허용구간입니다.",
            )

        return check_time_range(
            request_datetime=request_datetime,
            parsed_range=parsed_range,
            condition_name="평일",
        )

    # --------------------------------------------------
    # 5. 주말 조건 처리
    # --------------------------------------------------

    if has_weekend_text:
        if not is_current_weekend:
            return (
                False,
                "현재 날짜는 주말이 아닙니다.",
            )

        if has_24_hour_text:
            return (
                True,
                "주말 24시간 허용구간입니다.",
            )

        return check_time_range(
            request_datetime=request_datetime,
            parsed_range=parsed_range,
            condition_name="주말",
        )

    # --------------------------------------------------
    # 6. 토요일 조건 처리
    # --------------------------------------------------

    if has_saturday_text:
        if not is_current_saturday:
            return (
                False,
                "현재 날짜는 토요일이 아닙니다.",
            )

        if has_24_hour_text:
            return (
                True,
                "토요일 24시간 허용구간입니다.",
            )

        return check_time_range(
            request_datetime=request_datetime,
            parsed_range=parsed_range,
            condition_name="토요일",
        )

    # --------------------------------------------------
    # 7. 일요일 조건 처리
    # --------------------------------------------------

    if has_sunday_text:
        if not is_current_sunday:
            return (
                False,
                "현재 날짜는 일요일이 아닙니다.",
            )

        if has_24_hour_text:
            return (
                True,
                "일요일 24시간 허용구간입니다.",
            )

        return check_time_range(
            request_datetime=request_datetime,
            parsed_range=parsed_range,
            condition_name="일요일",
        )

    # --------------------------------------------------
    # 8. 요일 조건 없는 24시간 처리
    # --------------------------------------------------

    if (
        has_24_hour_text
        and not has_day_condition(cleaned)
    ):
        return (
            True,
            "24시간 허용구간입니다.",
        )

    # --------------------------------------------------
    # 9. 요일 조건 없는 일반 시간 범위 처리
    # --------------------------------------------------

    if parsed_range is not None:
        start_time, end_time = parsed_range

        is_allowed = is_time_within_range(
            target_time=request_datetime.time(),
            start_time=start_time,
            end_time=end_time,
        )

        start_text = start_time.strftime("%H:%M")
        end_text = end_time.strftime("%H:%M")

        if is_allowed:
            return (
                True,
                (
                    "현재 시간이 허용시간 "
                    f"{start_text}~{end_text} "
                    "범위에 포함됩니다."
                ),
            )

        return (
            False,
            (
                "현재 시간이 허용시간 "
                f"{start_text}~{end_text} "
                "범위에 포함되지 않습니다."
            ),
        )

    return (
        None,
        "허용시간 문자열을 해석할 수 없습니다.",
    )


def check_allowed_time(
    allowed_time_text: str,
    request_datetime: datetime | None,
    is_public_holiday: bool | None = None,
) -> bool | None:
    """
    허용 여부만 반환하는 호환용 함수.
    """

    result, _ = check_allowed_time_detail(
        allowed_time_text=allowed_time_text,
        request_datetime=request_datetime,
        is_public_holiday=is_public_holiday,
    )

    return result


def get_segment_id(
    row: Any,
    fallback_index: int,
) -> str:
    source_index = get_row_value(
        row,
        [
            "인덱스",
            "INDEX",
            "index",
        ],
    )

    if source_index:
        return source_index

    return str(fallback_index + 1)


def create_candidate(
    row: Any,
    row_index: int,
    destination_latitude: float,
    destination_longitude: float,
    nearest_point_wgs84: Point,
    distance_m: float,
    request_datetime: datetime | None,
    is_public_holiday: bool | None,
) -> ParkingSegmentCandidate:
    allowed_time = get_row_value(
        row,
        [
            "시간",
            "허용시간",
            "운영시간",
            "TIME",
        ],
    )

    is_time_allowed, time_check_reason = (
        check_allowed_time_detail(
            allowed_time_text=allowed_time,
            request_datetime=request_datetime,
            is_public_holiday=is_public_holiday,
        )
    )

    return ParkingSegmentCandidate(
        segment_id=get_segment_id(
            row=row,
            fallback_index=row_index,
        ),
        district=get_row_value(
            row,
            [
                "구",
                "자치구",
                "시군구",
                "구명",
                "SIGUNGU",
            ],
        ),
        segment_name=get_row_value(
            row,
            [
                "구간",
                "구간명",
                "도로명",
                "노선명",
                "위치",
                "ROAD_NAME",
            ],
        ),
        code=get_row_value(
            row,
            [
                "코드",
                "구간코드",
                "관리번호",
                "CODE",
            ],
        ),
        category=get_row_value(
            row,
            [
                "용도",
                "허용용도",
                "주정차용도",
                "유형",
                "종류",
                "CATEGORY",
            ],
        ),
        usage_code=get_row_value(
            row,
            [
                "구분",
                "구분코드",
                "유형코드",
            ],
        ),
        allowed_time=allowed_time,
        allowed_date=get_row_value(
            row,
            [
                "허용일",
                "허용날짜",
                "날짜",
                "DATE",
            ],
        ),
        stop_latitude=float(
            nearest_point_wgs84.y
        ),
        stop_longitude=float(
            nearest_point_wgs84.x
        ),
        destination_latitude=(
            destination_latitude
        ),
        destination_longitude=(
            destination_longitude
        ),
        distance_m=round(
            float(distance_m),
            2,
        ),
        geometry_type=row.geometry.geom_type,
        is_time_allowed=is_time_allowed,
        time_check_reason=time_check_reason,
    )


def find_nearby_parking_segments(
    latitude: float,
    longitude: float,
    search_radius_m: float = 1000.0,
    limit: int = 5,
    request_datetime: datetime | None = None,
    only_time_allowed: bool = False,
    is_public_holiday: bool | None = None,
) -> list[dict[str, Any]]:
    """
    목적지 주변의 주정차 허용구간을 가까운 순서로 반환한다.

    latitude:
        목적지 위도

    longitude:
        목적지 경도

    search_radius_m:
        검색 반경, 단위는 미터

    limit:
        반환할 최대 후보 개수

    request_datetime:
        허용시간 판별 기준 일시

    only_time_allowed:
        True이면 현재 시간에 허용된 구간만 반환

    is_public_holiday:
        True이면 공휴일
        False이면 공휴일 아님
        None이면 공휴일 여부를 알 수 없음
    """

    validate_coordinate(
        latitude=latitude,
        longitude=longitude,
    )

    if search_radius_m <= 0:
        raise ValueError(
            "검색 반경은 0보다 커야 합니다."
        )

    if limit <= 0:
        raise ValueError(
            "후보 개수는 0보다 커야 합니다."
        )

    source_gdf = (
        load_parking_allowed_geodataframe()
    )

    if source_gdf.empty:
        return []

    destination_gdf = (
        create_destination_geodataframe(
            latitude=latitude,
            longitude=longitude,
        )
    )

    segments_metric = source_gdf.to_crs(
        DISTANCE_CRS
    )

    destination_metric = (
        destination_gdf.to_crs(
            DISTANCE_CRS
        )
    )

    destination_point_metric = (
        destination_metric.geometry.iloc[0]
    )

    search_area = (
        destination_point_metric.buffer(
            search_radius_m
        )
    )

    nearby_mask = (
        segments_metric.geometry.intersects(
            search_area
        )
    )

    nearby_metric = segments_metric[
        nearby_mask
    ].copy()

    if nearby_metric.empty:
        return []

    nearby_metric["distance_m"] = (
        nearby_metric.geometry.distance(
            destination_point_metric
        )
    )

    nearby_metric = nearby_metric[
        nearby_metric["distance_m"]
        <= search_radius_m
    ].copy()

    if nearby_metric.empty:
        return []

    nearby_metric = nearby_metric.sort_values(
        by="distance_m",
        ascending=True,
    )

    candidates: list[
        ParkingSegmentCandidate
    ] = []

    for row_index, row in nearby_metric.iterrows():
        segment_geometry_metric = row.geometry

        _, nearest_segment_point_metric = (
            nearest_points(
                destination_point_metric,
                segment_geometry_metric,
            )
        )

        nearest_point_gdf = gpd.GeoDataFrame(
            geometry=[
                nearest_segment_point_metric
            ],
            crs=DISTANCE_CRS,
        )

        nearest_point_wgs84 = (
            nearest_point_gdf
            .to_crs(WGS84_CRS)
            .geometry
            .iloc[0]
        )

        candidate = create_candidate(
            row=row,
            row_index=int(row_index),
            destination_latitude=latitude,
            destination_longitude=longitude,
            nearest_point_wgs84=(
                nearest_point_wgs84
            ),
            distance_m=float(
                row["distance_m"]
            ),
            request_datetime=request_datetime,
            is_public_holiday=(
                is_public_holiday
            ),
        )

        if (
            only_time_allowed
            and candidate.is_time_allowed is not True
        ):
            continue

        candidates.append(candidate)

        if len(candidates) >= limit:
            break

    return [
        candidate.to_dict()
        for candidate in candidates
    ]


def find_nearest_parking_segment(
    latitude: float,
    longitude: float,
    search_radius_m: float = 1000.0,
    request_datetime: datetime | None = None,
    only_time_allowed: bool = False,
    is_public_holiday: bool | None = None,
) -> dict[str, Any] | None:
    """
    목적지와 가장 가까운 허용구간 한 개를 반환한다.
    """

    candidates = find_nearby_parking_segments(
        latitude=latitude,
        longitude=longitude,
        search_radius_m=search_radius_m,
        limit=1,
        request_datetime=request_datetime,
        only_time_allowed=only_time_allowed,
        is_public_holiday=is_public_holiday,
    )

    if not candidates:
        return None

    return candidates[0]


def print_candidate_result(
    candidate: dict[str, Any],
) -> None:
    print("-" * 60)

    for key, value in candidate.items():
        print(f"{key}: {value}")

    print("-" * 60)


def run_time_parser_test() -> None:
    """
    허용시간 문자열 판정 테스트.
    """

    test_datetime = datetime.now()

    test_cases = [
        "11:30∼14:00 (점심시간)",
        "09:00~18:00 (시간제 주차허용)",
        "20:00∼07:00 (시간제 주차허용)",
        "매일(24시간) 노상주차장설치",
        "09:00∼18:00 (평일) 공휴일 24시간",
        "평일 09:00~18:00",
        "주말 10:00~17:00",
        "토요일 09:00~13:00",
        "일요일 09:00~13:00",
        "공휴일 24시간",
    ]

    print("=" * 60)
    print("허용시간 문자열 판별 테스트")
    print("=" * 60)

    print(
        "기준 일시:",
        test_datetime.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    for test_case in test_cases:
        result, reason = (
            check_allowed_time_detail(
                allowed_time_text=test_case,
                request_datetime=test_datetime,
                is_public_holiday=False,
            )
        )

        print("-" * 60)
        print(f"문자열: {test_case}")
        print(f"판별 결과: {result}")
        print(f"판별 이유: {reason}")


def run_special_case_test() -> None:
    """
    평일 시간제 + 공휴일 24시간 조건을
    고정된 날짜와 시간으로 검증한다.
    """

    allowed_text = (
        "09:00∼18:00 (평일) 공휴일 24시간"
    )

    test_cases = [
        {
            "name": "평일 오전",
            "datetime": datetime(
                2026,
                7,
                30,
                10,
                0,
            ),
            "is_public_holiday": False,
        },
        {
            "name": "평일 저녁",
            "datetime": datetime(
                2026,
                7,
                30,
                19,
                0,
            ),
            "is_public_holiday": False,
        },
        {
            "name": "공휴일 저녁",
            "datetime": datetime(
                2026,
                7,
                30,
                19,
                0,
            ),
            "is_public_holiday": True,
        },
    ]

    print("=" * 60)
    print("복합 허용시간 조건 테스트")
    print("=" * 60)

    print(f"허용조건: {allowed_text}")

    for test_case in test_cases:
        result, reason = (
            check_allowed_time_detail(
                allowed_time_text=allowed_text,
                request_datetime=(
                    test_case["datetime"]
                ),
                is_public_holiday=(
                    test_case[
                        "is_public_holiday"
                    ]
                ),
            )
        )

        print("-" * 60)
        print(f"테스트: {test_case['name']}")
        print(
            "기준 일시:",
            test_case["datetime"].strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )
        print(
            "공휴일 여부:",
            test_case["is_public_holiday"],
        )
        print(f"판별 결과: {result}")
        print(f"판별 이유: {reason}")


def run_search_test() -> None:
    """
    대전역 인근 좌표 검색 테스트.
    """

    test_latitude = 36.332315
    test_longitude = 127.434447

    print("=" * 60)
    print("목적지 주변 주정차 허용구간 검색 테스트")
    print("=" * 60)

    print(f"목적지 위도: {test_latitude}")
    print(f"목적지 경도: {test_longitude}")

    results = find_nearby_parking_segments(
        latitude=test_latitude,
        longitude=test_longitude,
        search_radius_m=3000,
        limit=5,
        request_datetime=datetime.now(),
        only_time_allowed=False,
        is_public_holiday=False,
    )

    print(f"검색 결과 수: {len(results)}")

    if not results:
        print(
            "검색 반경 내 허용구간이 없습니다."
        )
        return

    for index, candidate in enumerate(
        results,
        start=1,
    ):
        print(f"\n후보 {index}")
        print_candidate_result(candidate)


def run_test() -> None:
    run_time_parser_test()

    print("\n")

    run_special_case_test()

    print("\n")

    run_search_test()


if __name__ == "__main__":
    try:
        run_test()

    except Exception as error:
        print(
            "[주정차 허용구간 검색 실패]"
        )
        print(error)
        raise