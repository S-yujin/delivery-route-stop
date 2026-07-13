"""
파일명 : optimize.py

역할
- 프론트엔드 요청을 받는 배송 경로 API Router
- 주소를 좌표로 변환하는 API 제공
- 두 좌표 사이 거리와 이동시간 조회 API 제공
- Service 처리 결과를 JSON으로 반환

현재 API
- POST /api/routes/geocode
- POST /api/routes/directions

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