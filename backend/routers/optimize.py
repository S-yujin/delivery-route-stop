"""
파일명 : optimize.py

역할
- 프론트엔드 요청을 받는 배송 경로 API Router
- 주소를 좌표로 변환하는 API 제공
- 두 좌표 사이 거리와 이동시간 조회 API 제공
- 배송지와 정차 후보지를 비교해 추천 정차지를 반환
- Service 처리 결과를 JSON으로 반환

현재 API
- POST /api/routes/geocode
- POST /api/routes/directions
- POST /api/routes/optimize

담당
- Backend / Data
"""

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field

from services.optimization_service import calculate_route
from services.optimization_service import (
    convert_address_to_coordinate,
)
from services.optimization_service import (
    optimize_delivery_stop,
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

    name: str = Field(
        ...,
        min_length=1,
        description="정차 후보지 이름",
        examples=["대전역 서광장 정차 후보지"],
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

    max_stop_minutes: int = Field(
        default=0,
        ge=0,
        description="최대 정차 가능 시간(분)",
    )

    road_width_score: int = Field(
        default=0,
        ge=0,
        le=5,
        description="도로 폭 점수",
    )

    safety_score: int = Field(
        default=0,
        ge=0,
        le=5,
        description="안전성 점수",
    )


class OptimizeRequest(BaseModel):
    """
    최적 정차지 추천 요청 구조
    """

    destinations: list[Destination] = Field(
        ...,
        min_length=1,
        description="배송지 목록",
    )

    stop_candidates: list[StopCandidate] = Field(
        ...,
        min_length=1,
        description="정차 후보지 목록",
    )


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
    배송지와 정차 후보지를 입력받아
    가장 적합한 정차 후보지와 배송 순서를 반환한다.

    현재는 배송 물량 가중치를 적용한
    직선거리 기반 임시 추천 로직을 사용한다.
    """

    try:
        destinations = [
            destination.model_dump()
            for destination in request.destinations
        ]

        stop_candidates = [
            candidate.model_dump()
            for candidate in request.stop_candidates
        ]

        result = optimize_delivery_stop(
            destinations=destinations,
            stop_candidates=stop_candidates,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["message"],
            )

        return result

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "배송 경로 최적화 중 오류가 발생했습니다: "
                f"{str(error)}"
            ),
        ) from error