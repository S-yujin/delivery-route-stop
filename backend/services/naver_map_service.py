"""
파일명 : naver_map_service.py

역할
- 네이버 Maps API와 통신하는 Service
- 주소를 좌표로 변환
- 좌표를 주소로 변환
- 두 좌표 사이의 차량 경로, 거리, 이동시간 조회

사용 API
- Geocoding
- Reverse Geocoding
- Directions 15

담당
- Backend / Data
"""

import os
from typing import Any

import requests
from dotenv import load_dotenv


# backend/.env 파일의 환경변수를 불러온다.
load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

GEOCODING_URL = (
    "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
)

REVERSE_GEOCODING_URL = (
    "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"
)

DIRECTIONS_URL = (
    "https://maps.apigw.ntruss.com/map-direction-15/v1/driving"
)


def get_headers() -> dict[str, str]:
    """
    네이버 Maps API 공통 인증 헤더를 생성한다.

    Returns
    -------
    dict[str, str]
        네이버 Maps API 인증 헤더
    """

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError(
            "NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 "
            ".env 파일에 설정되지 않았습니다."
        )

    return {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
    }


def geocode(address: str) -> dict[str, Any]:
    """
    주소를 위도와 경도로 변환한다.

    Parameters
    ----------
    address : str
        검색할 도로명 주소 또는 지번 주소

    Returns
    -------
    dict[str, Any]
        네이버 Geocoding API 원본 응답
    """

    response = requests.get(
        GEOCODING_URL,
        headers=get_headers(),
        params={
            "query": address,
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def reverse_geocode(
    longitude: float,
    latitude: float,
) -> dict[str, Any]:
    """
    위도와 경도를 주소로 변환한다.

    Parameters
    ----------
    longitude : float
        경도

    latitude : float
        위도

    Returns
    -------
    dict[str, Any]
        네이버 Reverse Geocoding API 원본 응답
    """

    response = requests.get(
        REVERSE_GEOCODING_URL,
        headers=get_headers(),
        params={
            "coords": f"{longitude},{latitude}",
            "output": "json",
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def get_directions(
    start_longitude: float,
    start_latitude: float,
    goal_longitude: float,
    goal_latitude: float,
) -> dict[str, Any]:
    """
    출발 좌표와 도착 좌표 사이의 차량 경로를 조회한다.

    좌표 순서는 반드시 '경도,위도' 순서로 전달한다.

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
        네이버 Directions 15 API 원본 응답
    """

    response = requests.get(
        DIRECTIONS_URL,
        headers=get_headers(),
        params={
            "start": f"{start_longitude},{start_latitude}",
            "goal": f"{goal_longitude},{goal_latitude}",
            "option": "traoptimal",
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()