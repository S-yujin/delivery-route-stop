import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  getDirections,
  getNextStop,
} from "../api/routeApi";
import MapView from "../components/MapView";
import StopCandidatePanel from "../components/StopCandidatePanel";

function ResultPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const inputData = location.state;

  const {
    start,
    destinations = [],
    vehicleType,
    departureTime,
    startLocation,
    destinationLocations = [],
    directionsResult,
    routePlan,
    vehicleRouteStops = [],
  } = inputData ?? {};

  const [currentPosition, setCurrentPosition] = useState(() =>
    startLocation
      ? {
          latitude: startLocation.latitude,
          longitude: startLocation.longitude,
        }
      : null
  );

  const [completedDestinationIds, setCompletedDestinationIds] = useState([]);
  const [nextStopResult, setNextStopResult] = useState(null);
  const [activeDirectionsResult,setActiveDirectionsResult,] = useState(directionsResult);
  const [isNextStopLoading, setIsNextStopLoading] = useState(false);

  if (!inputData) {
    return (
      <main>
        <div className="empty-result">
          <h1>입력 정보가 없습니다.</h1>
          <p>출발지와 배송지를 입력한 뒤 다시 시도해주세요.</p>
          <button
            className="full-width-button"
            type="button"
            onClick={() => navigate("/")}
          >
            입력 화면으로 이동
          </button>
        </div>
      </main>
    );
  }

  const vehicleLabels = {
    "small-truck": "소형 화물차",
    van: "승합차",
    motorcycle: "이륜차",
  };

  const recommendedDeliveryOrder =
    routePlan?.recommended_delivery_order ?? [];

  const responseNextDestination =
    nextStopResult?.next_destination ??
    (nextStopResult?.destination_id
      ? {
          destination_id: nextStopResult.destination_id,
          destination_name: nextStopResult.destination_name,
        }
      : null);

  const allRecommendedCompleted =
    recommendedDeliveryOrder.length > 0 &&
    recommendedDeliveryOrder.every((delivery) =>
      completedDestinationIds.includes(delivery.destination_id)
    );

  const isDeliveryCompleted =
    nextStopResult?.completed === true || allRecommendedCompleted;

  const currentDestinationId = isDeliveryCompleted
    ? null
    : responseNextDestination?.destination_id ??
      routePlan?.next_stop?.destination_id ??
      recommendedDeliveryOrder.find(
        (delivery) =>
          !completedDestinationIds.includes(delivery.destination_id)
      )?.destination_id ??
      null;

  const currentDestinationInfo = destinationLocations.find(
    (destination) => destination.id === currentDestinationId
  );

  const currentDestinationName =
    responseNextDestination?.destination_name ??
    recommendedDeliveryOrder.find(
      (delivery) => delivery.destination_id === currentDestinationId
    )?.destination_name ??
    currentDestinationInfo?.address ??
    currentDestinationId;

  const responseNextStop =
    nextStopResult?.next_stop?.selected_stop ??
    nextStopResult?.next_stop ??
    nextStopResult?.selected_stop ??
    null;

  const routeSelectedStop =
    vehicleRouteStops.find(
      (stop) => stop.destinationId === currentDestinationId
    ) ?? null;

  const selectedStopEntry = routePlan?.selected_stops?.find(
    (stop) => stop.destination_id === currentDestinationId
  );

  const currentDestinationResult = routePlan?.destination_results?.find(
    (result) => result.destination_id === currentDestinationId
  );

  const initialSelectedStop = routeSelectedStop
    ? {
        candidate_id: routeSelectedStop.id,
        destination_id: routeSelectedStop.destinationId,
        candidate_name: routeSelectedStop.name,
        address: routeSelectedStop.address,
        latitude: routeSelectedStop.latitude,
        longitude: routeSelectedStop.longitude,
      }
    : selectedStopEntry?.selected_stop ??
      selectedStopEntry ??
      currentDestinationResult?.recommended_stop ??
      routePlan?.next_stop?.selected_stop ??
      routePlan?.selected_stop ??
      null;

  const activeSelectedStop = isDeliveryCompleted
    ? null
    : responseNextStop ?? initialSelectedStop;

  const baseStopCandidates =
    routePlan?.destination_results?.flatMap((destinationResult) =>
      (destinationResult.candidate_rankings ?? []).map((candidate) => ({
        id: candidate.candidate_id,
        type: "stop",
        destinationId: candidate.destination_id,
        name: candidate.candidate_name,
        address: candidate.address,
        latitude: candidate.latitude,
        longitude: candidate.longitude,
        score:
          candidate.dynamic_total_score ?? candidate.total_score ?? 0,
        walkingDistance: candidate.walking_distance_m,
        walkingTime: candidate.walking_time_minutes,
        rank: candidate.rank,
        maxStopMinutes: candidate.max_stop_minutes,
        reason:
          candidate.walking_distance_m !== undefined
            ? `배송지까지 도보 ${candidate.walking_distance_m}m`
            : null,
      }))
    ) ?? [];

  const normalizedActiveStop = activeSelectedStop
    ? {
        id: activeSelectedStop.candidate_id,
        type: "selected-stop",
        destinationId:
          activeSelectedStop.destination_id ?? currentDestinationId,
        name:
          activeSelectedStop.candidate_name ??
          activeSelectedStop.name ??
          "추천 정차지",
        address: activeSelectedStop.address,
        latitude: activeSelectedStop.latitude,
        longitude: activeSelectedStop.longitude,
        score:
          activeSelectedStop.dynamic_total_score ??
          activeSelectedStop.total_score ??
          activeSelectedStop.score ??
          0,
        walkingDistance: activeSelectedStop.walking_distance_m,
        walkingTime: activeSelectedStop.walking_time_minutes,
        rank: activeSelectedStop.rank,
        maxStopMinutes: activeSelectedStop.max_stop_minutes,
        reason:
          activeSelectedStop.walking_distance_m !== undefined
            ? `배송지까지 도보 ${activeSelectedStop.walking_distance_m}m`
            : "현재 추천된 정차지입니다.",
      }
    : null;

  const currentDestinationCandidates = baseStopCandidates.filter(
    (candidate) => candidate.destinationId === currentDestinationId
  );

  const currentStopCandidates = isDeliveryCompleted
    ? []
    : [
        ...currentDestinationCandidates
          .filter(
            (candidate) =>
              !(
                candidate.id === normalizedActiveStop?.id &&
                candidate.destinationId ===
                  normalizedActiveStop?.destinationId
              )
          )
          .map((candidate) => ({ ...candidate, type: "stop" })),
        ...(normalizedActiveStop ? [normalizedActiveStop] : []),
      ];

  const remainingCount = isDeliveryCompleted
    ? 0
    : Number(
        nextStopResult?.remaining_count ??
          Math.max(
            recommendedDeliveryOrder.length - completedDestinationIds.length,
            0
          )
      );

  const unresolvedDestinationIds =
    routePlan?.unresolved_destination_ids ?? [];

  const hasRecommendedOrder = recommendedDeliveryOrder.length > 0;

  const routeSummary = {
    totalDistanceKm: Number(directionsResult?.totalDistanceKm ?? 0),
    estimatedTimeMinutes: Math.round(
      Number(directionsResult?.totalDurationMinutes ?? 0)
    ),
    candidateCount: currentStopCandidates.length,
  };


  const visibleDestinationLocations =
    destinationLocations.filter(
    (destination) =>
      !completedDestinationIds.includes(
        destination.id
      )
  );

  const updateCurrentPosition = () =>
    new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("현재 위치 기능을 사용할 수 없습니다."));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          const nextPosition = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          };

          setCurrentPosition(nextPosition);
          resolve(nextPosition);
        },
        () => {
          reject(new Error("현재 차량 위치를 불러오지 못했습니다."));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
        }
      );
    });

  const handleDeliveryComplete = async () => {
    if (!currentDestinationId) {
      alert("현재 완료할 배송지가 없습니다.");
      return;
    }

    if (!routePlan) {
      alert("배송 계획 정보가 없습니다.");
      return;
    }

    const nextCompletedDestinationIds = completedDestinationIds.includes(
      currentDestinationId
    )
      ? completedDestinationIds
      : [...completedDestinationIds, currentDestinationId];

    setIsNextStopLoading(true);

    try {
      let latestPosition = currentPosition;

      try {
        latestPosition = await updateCurrentPosition();
      } catch (locationError) {
        console.warn("GPS 조회 실패, 기존 위치 사용:", locationError);
      }

      if (!latestPosition) {
        throw new Error("현재 차량 위치 정보가 없습니다.");
      }

      const response = await getNextStop({
        current_position: latestPosition,
        completed_destination_ids: nextCompletedDestinationIds,
        plan: routePlan,
      });

      const responseNextStop =
        response?.next_stop?.selected_stop ??
        response?.next_stop ??
        response?.selected_stop ??
        null;

      if (
        responseNextStop?.latitude !== undefined &&
        responseNextStop?.longitude !== undefined
      ) {

      /*
       * 배송 완료 당시 차량은 현재 추천 정차지에
       * 있다고 보고 다음 정차지까지 경로 계산
       */
      
      const routeStart = normalizedActiveStop ? {
          latitude:
            normalizedActiveStop.latitude,
          longitude:
            normalizedActiveStop.longitude,
        }
      : latestPosition;

      const nextDirections =
        await getDirections( routeStart,
        {
          latitude:
            responseNextStop.latitude,
          longitude:
            responseNextStop.longitude,
        }
      );

       setActiveDirectionsResult({
         totalDistanceKm: Number(
           nextDirections.distance_km ?? 0
         ),

         totalDurationMinutes: Number(
         nextDirections.duration_minutes ?? 0
         ),

         path: nextDirections.path ?? [],
       });
     }

      setCompletedDestinationIds(nextCompletedDestinationIds);
      setNextStopResult(response);

      console.log("Next Stop 응답:", response);
    } catch (error) {
      const errorMessage = error?.message ?? "";

      if (errorMessage.includes("남은 배송지가 없습니다")) {
        setCompletedDestinationIds(nextCompletedDestinationIds);
        setNextStopResult({
          completed: true,
          next_destination: null,
          next_stop: null,
          remaining_count: 0,
        });

        setActiveDirectionsResult({
          totalDistanceKm: 0,
          totalDurationMinutes: 0,
          path: [],
        });

        console.log("모든 배송 완료:", nextCompletedDestinationIds);
        return;
      }

      console.error("다음 정차지 요청 실패:", error);
      alert(errorMessage || "다음 정차지를 불러오지 못했습니다.");
    } finally {
      setIsNextStopLoading(false);
    }
  };

  return (
    <main>
      <div className="page-header">
        <div>
          <h1>추천 결과</h1>
          <p>입력한 배송 정보를 기준으로 추천 결과를 표시합니다.</p>
        </div>

        <button
          className="full-width-button"
          type="button"
          onClick={() => navigate("/")}
        >
          다시 입력하기
        </button>
      </div>

      <section className="input-summary">
        <h2>배송 정보</h2>

        <div className="summary-item">
          <span>출발지</span>
          <strong>{start}</strong>
        </div>

        <div className="summary-item">
          <span>배송지 수</span>
          <strong>{destinations.length}곳</strong>
        </div>

        <div className="summary-item">
          <span>차량 종류</span>
          <strong>{vehicleLabels[vehicleType] ?? vehicleType}</strong>
        </div>

        <div className="summary-item">
          <span>출발 예정 시각</span>
          <strong>{departureTime || "미지정"}</strong>
        </div>

        <div className="destination-summary-list">
          <h3>입력한 배송지</h3>

          {destinations.map((destination, index) => (
            <div
              className="destination-summary-item"
              key={`${destination}-${index}`}
            >
              <span>{index + 1}</span>
              <p>{destination}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="result-summary-section">
        <article className="result-summary-card">
          <span>총 거리</span>
          <strong>{routeSummary.totalDistanceKm.toFixed(1)}km</strong>
        </article>

        <article className="result-summary-card">
          <span>예상 시간</span>
          <strong>{routeSummary.estimatedTimeMinutes}분</strong>
        </article>

        <article className="result-summary-card">
          <span>정차 후보</span>
          <strong>{routeSummary.candidateCount}곳</strong>
        </article>
      </section>

      <section className="map-section">
        <div className="section-heading">
          <h2>배송 경로 지도</h2>
          <p>추천 경로와 배송지 위치를 확인할 수 있습니다.</p>
        </div>

        <MapView
          startLocation={startLocation}
          destinationLocations={visibleDestinationLocations}
          directionsResult={activeDirectionsResult}
          stopCandidates={currentStopCandidates}
        />
      </section>

      <section className="route-order-section">
        <div className="section-heading">
          <h2>추천 배송 순서</h2>
          <p>정차 가능한 후보지를 기준으로 계산한 배송 순서입니다.</p>
        </div>

        <div className="route-order-list">
          <div className="route-order-item route-start-item">
            <span className="route-order-badge start-badge">출발</span>
            <div className="route-order-content">
              <strong>{start}</strong>
              <span>배송 시작 위치</span>
            </div>
          </div>

          {hasRecommendedOrder ? (
            recommendedDeliveryOrder.map((delivery) => {
              const destinationInfo = destinationLocations.find(
                (destination) =>
                  destination.id === delivery.destination_id
              );

              const isCompleted = completedDestinationIds.includes(
                delivery.destination_id
              );

              const isCurrent =
                currentDestinationId === delivery.destination_id;

              const itemClassName = [
                "route-order-item",
                isCompleted ? "completed" : "",
                isCurrent ? "current" : "",
              ]
                .filter(Boolean)
                .join(" ");

              return (
                <div
                  className={itemClassName}
                  key={delivery.destination_id}
                >
                  <span className="route-order-badge">{delivery.order}</span>

                  <div className="route-order-content">
                    <strong>
                      {destinationInfo?.address ??
                        delivery.destination_name ??
                        delivery.destination_id}
                    </strong>

                    <span>
                      {isCompleted
                        ? "배송 완료"
                        : isCurrent
                          ? "현재 배송 대상"
                          : `${delivery.order}번째 배송지`}
                    </span>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="empty-candidates">
              <strong>추천 가능한 배송 순서를 만들지 못했습니다.</strong>
              <p>배송지 주변에 조건을 만족하는 정차 후보지가 없습니다.</p>
            </div>
          )}
        </div>

        {unresolvedDestinationIds.length > 0 && (
          <div className="empty-candidates">
            <p>
              정차 후보를 찾지 못한 배송지:{" "}
              {unresolvedDestinationIds.join(", ")}
            </p>
          </div>
        )}
      </section>

      {(hasRecommendedOrder || nextStopResult) && (
        <section className="delivery-progress-section">
          <h2>배송 진행</h2>

          {isDeliveryCompleted ? (
            <div className="delivery-completed-box">
              <strong>모든 배송이 완료되었습니다.</strong>
              <p>
                총 {completedDestinationIds.length}곳의 배송을 완료했습니다.
              </p>

              <button
                className="full-width-button"
                type="button"
                onClick={() => navigate("/")}
              >
                새로운 배송 시작
              </button>
            </div>
          ) : (
            <>
              <div className="delivery-current-info">
                <span>현재 배송 대상</span>
                <strong>{currentDestinationName ?? currentDestinationId}</strong>

                {normalizedActiveStop && (
                  <p>추천 정차지: {normalizedActiveStop.name}</p>
                )}
              </div>

              <p>
                남은 배송지: <strong>{remainingCount}곳</strong>
              </p>

              <p>
                완료된 배송지:{" "}
                <strong>{completedDestinationIds.length}곳</strong>
              </p>

              <button
                className="full-width-button"
                type="button"
                onClick={handleDeliveryComplete}
                disabled={isNextStopLoading || !currentDestinationId}
              >
                {isNextStopLoading
                  ? "다음 정차지를 계산 중입니다."
                  : "현재 배송 완료"}
              </button>
            </>
          )}
        </section>
      )}

      <StopCandidatePanel stopCandidates={currentStopCandidates} />
    </main>
  );
}

export default ResultPage;