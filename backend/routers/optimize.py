"""
파일명: optimize.py

역할
- 프론트엔드 요청을 받는 배송 경로 API Router
- 주소를 좌표로 변환하는 API 제공
- 두 좌표 사이 거리와 이동시간 조회 API 제공
- 배송지별 정차 후보지를 평가해 추천 정차지를 반환
- 추천 정차지를 기준으로 배송 순서를 계산
- Service 처리 결과를 JSON으로 반환

현재 API
- POST /api/routes/geocode
- POST /api/routes/directions
- POST /api/routes/optimize

담당
- Backend / Data
"""

from datetime import datetime
from pathlib import Path
import sys

# backend 폴더에서 uvicorn app:app으로 실행할 때도
# parking_segment_service 내부의 backend.services import가 동작하도록
# 프로젝트 루트를 Python 모듈 검색 경로에 추가한다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field

from services.optimization_service import calculate_route
from services.optimization_service import (
    convert_address_to_coordinate,
)
from services.loading_stop_algorithm import (
    recommend_stops_from_parking_segments,
    select_next_stop_from_plan,
)
from services.parking_segment_service import (
    find_nearby_parking_segments,
)


router = APIRouter(
    prefix="/api/routes",
    tags=["배송 경로"],
)


class GeocodeRequest(BaseModel):
    """
    주소를 좌표로 변환할 때 사용하는 요청 구조
    """

    address: str = Field(
        ...,
        min_length=1,
        examples=["대전광역시 동구 중앙로 215"],
    )


class Coordinate(BaseModel):
    """
    하나의 위치 좌표 구조
    """

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="경도",
    )

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="위도",
    )


class DirectionsRequest(BaseModel):
    """
    차량 경로 조회 요청 구조
    """

    start: Coordinate
    goal: Coordinate


class VehicleProfile(BaseModel):
    """
    배송 차량의 제원 정보
    """

    vehicle_type: str = Field(
        default="small-truck",
        min_length=1,
        description="차량 종류",
        examples=["small-truck"],
    )

    width_m: float = Field(
        default=1.8,
        gt=0,
        description="차량 폭(m)",
    )

    height_m: float = Field(
        default=2.0,
        gt=0,
        description="차량 높이(m)",
    )

    side_clearance_m: float = Field(
        default=0.5,
        ge=0,
        description="차량 좌우에 필요한 여유 폭(m)",
    )


class Destination(BaseModel):
    """
    하나의 배송지 데이터 구조
    """

    id: str = Field(
        ...,
        min_length=1,
        description="배송지 고유 ID",
        examples=["D001"],
    )

    name: str = Field(
        ...,
        min_length=1,
        description="배송지 이름",
        examples=["대전역 배송지"],
    )

    address: str | None = Field(
        default=None,
        description="배송지 주소",
        examples=["대전광역시 동구 중앙로 215"],
    )

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="배송지 위도",
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="배송지 경도",
    )

    delivery_count: int = Field(
        default=1,
        ge=1,
        description="배송 물량",
    )

    service_time_minutes: int = Field(
        default=0,
        ge=0,
        description="배송 처리 예상 시간(분)",
    )


class StopCandidate(BaseModel):
    """
    하나의 정차 후보지 데이터 구조
    """

    id: str = Field(
        ...,
        min_length=1,
        description="정차 후보지 고유 ID",
        examples=["S001"],
    )

    destination_id: str | None = Field(
        default=None,
        description="정차 후보지가 연결된 배송지 ID",
        examples=["D001"],
    )

    name: str = Field(
        ...,
        min_length=1,
        description="정차 후보지 이름",
        examples=["대전역 서광장 정차 후보지"],
    )

    address: str | None = Field(
        default=None,
        description="정차 후보지 주소",
        examples=["대전광역시 동구 중앙로 215 인근"],
    )

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="정차 후보지 위도",
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="정차 후보지 경도",
    )

    parking_available: bool = Field(
        default=True,
        description="정차 가능 여부",
    )

    no_stopping_zone: bool = Field(
        default=False,
        description="정차 절대 금지 구역 여부",
    )

    stop_allowed_at_request_time: bool = Field(
        default=True,
        description="요청 시간대 정차 가능 여부",
    )

    vehicle_entry_allowed: bool = Field(
        default=True,
        description="차량 진입 가능 여부",
    )

    max_stop_minutes: int = Field(
        default=0,
        ge=0,
        description=(
            "최대 정차 가능 시간(분), "
            "0이면 제한 정보 없음"
        ),
    )

    road_width_m: float | None = Field(
        default=None,
        gt=0,
        description="실제 도로 폭(m)",
    )

    height_limit_m: float | None = Field(
        default=None,
        gt=0,
        description="차량 높이 제한(m)",
    )

    walking_distance_m: float | None = Field(
        default=None,
        ge=0,
        description="후보지에서 배송지까지 도보 거리(m)",
    )

    walking_time_minutes: float | None = Field(
        default=None,
        ge=0,
        description="후보지에서 배송지까지 도보 시간(분)",
    )

    legality_score: int = Field(
        default=5,
        ge=0,
        le=5,
        description="정차 적법성 점수",
    )

    congestion_score: int = Field(
        default=3,
        ge=0,
        le=5,
        description=(
            "교통 혼잡 적합도 점수, "
            "높을수록 정차에 유리"
        ),
    )

    data_quality: str = Field(
        default="sufficient",
        description=(
            "후보지 데이터 품질: "
            "sufficient, insufficient, missing, unreliable"
        ),
    )

    # 기존 요청 형식과의 호환성을 위한 필드
    road_width_score: int = Field(
        default=0,
        ge=0,
        le=5,
        description=(
            "기존 도로 폭 점수. "
            "road_width_m이 없을 때만 사용"
        ),
    )

    safety_score: int = Field(
        default=0,
        ge=0,
        le=5,
        description=(
            "기존 요청 형식 호환 필드. "
            "현재 추천 점수에는 사용하지 않음"
        ),
    )


class OptimizeRequest(BaseModel):
    """
    SHP 데이터 기반 최적 정차지 추천 요청 구조.

    프론트엔드는 출발지, 차량 정보, 배송지만 전달한다.
    정차 후보지는 백엔드가 배송지 주변 SHP 데이터에서 생성한다.
    """

    start: Coordinate | None = Field(
        default=None,
        description=(
            "배송 차량의 출발 좌표. "
            "입력 시 최근접 이웃 방식으로 배송 순서 계산"
        ),
    )

    vehicle: VehicleProfile = Field(
        default_factory=VehicleProfile,
        description="배송 차량 정보",
    )

    max_walking_distance_m: float = Field(
        default=300,
        gt=0,
        description=(
            "정차 후보지에서 배송지까지 허용하는 "
            "최대 도보 거리(m)"
        ),
    )

    search_radius_m: float = Field(
        default=1000,
        gt=0,
        description="배송지 주변 SHP 정차 후보 검색 반경(m)",
    )

    candidate_limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="배송지별 SHP 정차 후보 최대 개수",
    )

    request_datetime: datetime | None = Field(
        default=None,
        description=(
            "정차 허용 시간 판별 기준 일시. "
            "미입력 시 서비스 기본 기준 사용"
        ),
    )

    only_time_allowed: bool = Field(
        default=False,
        description=(
            "True이면 요청 시간에 정차가 허용된 "
            "SHP 구간만 후보로 사용"
        ),
    )

    is_public_holiday: bool | None = Field(
        default=None,
        description=(
            "공휴일 여부. 알 수 없으면 null"
        ),
    )

    destinations: list[Destination] = Field(
        ...,
        min_length=1,
        description="배송지 목록",
    )


class NextStopRequest(BaseModel):
    plan: dict
    current_position: Coordinate
    next_destination_id: str | None = None
    completed_destination_ids: list[str] = Field(default_factory=list)
    max_vehicle_distance_m: float = Field(default=5000.0, gt=0)



@router.post("/geocode")
def geocode_address(
    request: GeocodeRequest,
) -> dict:
    """
    주소를 입력받아 위도와 경도를 반환한다.
    """

    try:
        result = convert_address_to_coordinate(
            request.address,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=404,
                detail=result["message"],
            )

        return result

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "주소 변환 중 오류가 발생했습니다: "
                f"{str(error)}"
            ),
        ) from error


@router.post("/directions")
def directions(
    request: DirectionsRequest,
) -> dict:
    """
    출발 좌표와 도착 좌표를 입력받아
    차량 이동 거리와 예상 시간을 반환한다.
    """

    try:
        result = calculate_route(
            start_longitude=request.start.longitude,
            start_latitude=request.start.latitude,
            goal_longitude=request.goal.longitude,
            goal_latitude=request.goal.latitude,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=404,
                detail=result["message"],
            )

        return result

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "경로 조회 중 오류가 발생했습니다: "
                f"{str(error)}"
            ),
        ) from error


@router.post("/optimize")
def optimize_route(
    request: OptimizeRequest,
) -> dict:
    """
    배송지 좌표 주변의 SHP 주정차 허용구간을 조회하고,
    생성된 후보를 평가하여 추천 정차지와 배송 순서를 반환한다.

    처리 순서
    1. 프론트 요청의 배송지 데이터를 변환
    2. 배송지별 주변 SHP 주정차 허용구간 검색
    3. SHP 검색 결과를 정차 후보 형식으로 변환
    4. 하드 제약 및 점수 기준으로 추천 정차지 선정
    5. 출발지가 있으면 배송 순서 계산
    """

    try:
        destinations = [
            destination.model_dump()
            for destination in request.destinations
        ]

        vehicle_profile = request.vehicle.model_dump()

        start = (
            request.start.model_dump()
            if request.start is not None
            else None
        )

        parking_segments_by_destination: dict[
            str,
            list[dict],
        ] = {}

        candidate_counts: dict[str, int] = {}

        for destination in destinations:
            destination_id = str(destination["id"])

            parking_segments = find_nearby_parking_segments(
                latitude=destination["latitude"],
                longitude=destination["longitude"],
                search_radius_m=request.search_radius_m,
                limit=request.candidate_limit,
                request_datetime=request.request_datetime,
                only_time_allowed=request.only_time_allowed,
                is_public_holiday=request.is_public_holiday,
            )

            parking_segments_by_destination[
                destination_id
            ] = parking_segments
            candidate_counts[destination_id] = len(
                parking_segments
            )

        result = recommend_stops_from_parking_segments(
            destinations=destinations,
            parking_segments_by_destination=(
                parking_segments_by_destination
            ),
            vehicle_profile=vehicle_profile,
            max_walking_distance_m=(
                request.max_walking_distance_m
            ),
            start=start,
            max_candidates_per_destination=(
                request.candidate_limit
            ),
        )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result.get(
                    "message",
                    "배송 경로 최적화에 실패했습니다.",
                ),
            )

        # SHP 조회 결과를 프론트와 Swagger에서 확인할 수 있도록
        # 배송지별 검색 후보 개수를 응답에 함께 제공한다.
        result["shp_candidate_counts"] = candidate_counts
        result["search_radius_m"] = request.search_radius_m

        return result

    except HTTPException:
        raise

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "SHP 데이터를 찾지 못했습니다: "
                f"{str(error)}"
            ),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "배송 경로 최적화 중 오류가 발생했습니다: "
                f"{str(error)}"
            ),
        ) from error


@router.post("/next-stop")
def next_stop(request: NextStopRequest) -> dict:
    try:
        result = select_next_stop_from_plan(
            plan_result=request.plan,
            current_position=request.current_position.model_dump(),
            next_destination_id=request.next_destination_id,
            completed_destination_ids=request.completed_destination_ids,
            max_vehicle_distance_m=request.max_vehicle_distance_m,
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("message","다음 정차지를 선택하지 못했습니다."))
        return result
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"다음 정차지 선택 중 오류가 발생했습니다: {error}") from error