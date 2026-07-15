"""
파일명 : app.py

역할
- FastAPI 백엔드 서버의 시작 파일
- 배송 경로 관련 Router 등록
- 프론트엔드와의 통신을 위한 CORS 설정
- 서버 상태 확인 API 제공
- Swagger API 문서 제공

현재 연결 API
- GET  /
- GET  /health
- POST /api/routes/geocode
- POST /api/routes/directions
- POST /api/routes/optimize

담당
- Backend / Data
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.optimize import router as optimize_router


# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Delivery Route Stop API",
    description=(
        "대전 도심 다중 배송지 경로 및 "
        "하역 정차 추천 시스템"
    ),
    version="1.0.0",
)


# 프론트엔드와 백엔드 간 요청 허용
# 개발 단계에서는 React와 Vite의 localhost 주소를 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 배송 경로 관련 Router 등록
app.include_router(optimize_router)


@app.get(
    "/",
    tags=["서버 상태"],
)
def root() -> dict:
    """
    백엔드 서버 실행 여부를 확인한다.
    """

    return {
        "success": True,
        "message": (
            "Delivery Route Stop API 서버가 "
            "실행 중입니다."
        ),
        "version": app.version,
        "docs": "/docs",
        "available_apis": [
            "POST /api/routes/geocode",
            "POST /api/routes/directions",
            "POST /api/routes/optimize",
        ],
    }


@app.get(
    "/health",
    tags=["서버 상태"],
)
def health_check() -> dict:
    """
    서버 상태를 확인한다.
    """

    return {
        "success": True,
        "status": "healthy",
        "service": "delivery-route-stop-backend",
        "version": app.version,
    }