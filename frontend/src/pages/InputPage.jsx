import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  geocodeAddress,
  getDirections,
  optimizeRoute,
} from "../api/routeApi";

async function geocodeWithMessage(address, label) {
  try {
    return await geocodeAddress(address);
  } catch {
    throw new Error(
      `${label} 주소를 찾을 수 없습니다: ${address}`
    );
  }
}

function InputPage() {
  const navigate = useNavigate();

  const [start, setStart] = useState("");
  const [destinations, setDestinations] = useState([""]);
  const [vehicleType, setVehicleType] =
    useState("small-truck");
  const [departureTime, setDepartureTime] =
    useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleDestinationChange = (
    index,
    value
  ) => {
    const updatedDestinations = [
      ...destinations,
    ];

    updatedDestinations[index] = value;
    setDestinations(updatedDestinations);
  };

  const handleAddDestination = () => {
    setDestinations([
      ...destinations,
      "",
    ]);
  };

  const handleRemoveDestination = (index) => {
    if (destinations.length === 1) {
      return;
    }

    const updatedDestinations =
      destinations.filter(
        (_, destinationIndex) =>
          destinationIndex !== index
      );

    setDestinations(updatedDestinations);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedStart = start.trim();

    const validDestinations = destinations
      .map((destination) =>
        destination.trim()
      )
      .filter(
        (destination) =>
          destination !== ""
      );

    if (trimmedStart === "") {
      alert("출발지를 입력해주세요.");
      return;
    }

    if (validDestinations.length === 0) {
      alert(
        "배송지를 한 곳 이상 입력해주세요."
      );
      return;
    }

    if (departureTime === "") {
      alert(
        "출발 예정 시각을 입력해주세요."
      );
      return;
    }

    setIsLoading(true);

    try {
      const startGeocode =
        await geocodeWithMessage(
          trimmedStart,
          "출발지"
        );

      const destinationGeocodes =
        await Promise.all(
          validDestinations.map(
            (address, index) =>
              geocodeWithMessage(
                address,
                `배송지 ${index + 1}`
              )
          )
        );

      const startLocation = {
        id: "START",
        type: "start",
        name: "출발지",
        address: trimmedStart,
        latitude:
          startGeocode.latitude,
        longitude:
          startGeocode.longitude,
      };

      const destinationLocations =
        destinationGeocodes.map(
          (geocode, index) => ({
            id: `D${String(
              index + 1
            ).padStart(3, "0")}`,

            type: "destination",
            order: index + 1,
            name: `배송지 ${index + 1}`,

            address:
              validDestinations[index],

            latitude:
              geocode.latitude,

            longitude:
              geocode.longitude,

            delivery_count: 1,
            service_time_minutes: 10,
          })
        );

      const [hours, minutes] =
        departureTime
          .split(":")
          .map(Number);

      const requestDateTime =
        new Date();

      requestDateTime.setHours(
        hours,
        minutes,
        0,
        0
      );

      /*
       * 정차 후보 알고리즘 요청
       *
       * 현재 후보 생성 테스트를 위해
       * 도보 거리와 검색 반경을 넓힌 상태
       */
      const optimizeRequest = {
        start: {
          latitude:
            startLocation.latitude,

          longitude:
            startLocation.longitude,
        },

        vehicle: {
          vehicle_type: vehicleType,
          width_m: 1.8,
          height_m: 2,
          side_clearance_m: 0.5,
        },

        max_walking_distance_m: 700,
        search_radius_m: 1500,
        candidate_limit: 10,

        request_datetime:
          requestDateTime.toISOString(),

        only_time_allowed: false,
        is_public_holiday: false,

        destinations:
          destinationLocations.map(
            (destination) => ({
              id: destination.id,

              name:
                destination.address,

              address:
                destination.address,

              latitude:
                destination.latitude,

              longitude:
                destination.longitude,

              delivery_count:
                destination.delivery_count,

              service_time_minutes:
                destination
                  .service_time_minutes,
            })
          ),
      };

      const routePlan =
        await optimizeRoute(
          optimizeRequest
        );

      console.log(
        "Optimize 요청:",
        optimizeRequest
      );

      console.log(
        "Optimize 전체 응답:",
        routePlan
      );

      /*
       * 입력된 배송 순서 기준 도로 경로 요청
       */
      const routePoints = [
        startLocation,
        ...destinationLocations,
      ];

      const directionResults =
        await Promise.all(
          routePoints
            .slice(0, -1)
            .map((point, index) =>
              getDirections(
                point,
                routePoints[index + 1]
              )
            )
        );

      const totalDistanceKm =
        directionResults.reduce(
          (total, result) =>
            total +
            Number(
              result.distance_km ?? 0
            ),
          0
        );

      const totalDurationMinutes =
        directionResults.reduce(
          (total, result) =>
            total +
            Number(
              result.duration_minutes ?? 0
            ),
          0
        );

      const routePath =
        directionResults.flatMap(
          (result, index) => {
            const path =
              result.path ?? [];

            // 구간 경계의 중복 좌표 제거
            return index === 0
              ? path
              : path.slice(1);
          }
        );

      const directionsResult = {
        totalDistanceKm:
          Math.round(
            totalDistanceKm * 100
          ) / 100,

        totalDurationMinutes:
          Math.round(
            totalDurationMinutes * 10
          ) / 10,

        path: routePath,
      };

      console.log(
        "출발지 좌표:",
        startLocation
      );

      console.log(
        "배송지 좌표:",
        destinationLocations
      );

      console.log(
        "경로 응답:",
        directionsResult
      );

      navigate("/result", {
        state: {
          start: trimmedStart,

          destinations:
            validDestinations,

          vehicleType,
          departureTime,

          startLocation,
          destinationLocations,

          directionsResult,
          routePlan,
        },
      });
    } catch (error) {
      console.error(
        "경로 검색 실패:",
        error
      );

      alert(
        error.message ||
          "경로를 불러오는 중 오류가 발생했습니다."
      );

      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <main>
        <div className="loading-screen">
          <div className="loading-spinner" />

          <h1>
            추천 경로를 분석 중입니다.
          </h1>

          <p>
            주소와 도로 경로를 분석하고
            있습니다.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main>
      <header className="input-header">
        <h1>CurbRoute AI</h1>

        <p>
          배송 경로와 안전한 하역 정차
          위치를 추천합니다.
        </p>
      </header>

      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="start">
            출발지
          </label>

          <input
            id="start"
            type="text"
            value={start}
            onChange={(event) =>
              setStart(
                event.target.value
              )
            }
            placeholder="예: 대전역"
          />
        </div>

        <section className="destination-section">
          <div className="section-title-row">
            <label>배송지</label>

            <button
              type="button"
              className="add-destination-button"
              onClick={
                handleAddDestination
              }
            >
              + 배송지 추가
            </button>
          </div>

          <div className="destination-list">
            {destinations.map(
              (destination, index) => (
                <div
                  className="destination-row"
                  key={index}
                >
                  <span className="destination-number">
                    {index + 1}
                  </span>

                  <input
                    type="text"
                    value={destination}
                    onChange={(event) =>
                      handleDestinationChange(
                        index,
                        event.target.value
                      )
                    }
                    placeholder={`배송지 ${
                      index + 1
                    } 주소`}
                  />

                  <button
                    type="button"
                    className="remove-destination-button"
                    onClick={() =>
                      handleRemoveDestination(
                        index
                      )
                    }
                    disabled={
                      destinations.length ===
                      1
                    }
                    aria-label={`배송지 ${
                      index + 1
                    } 삭제`}
                  >
                    삭제
                  </button>
                </div>
              )
            )}
          </div>
        </section>

        <div>
          <label htmlFor="vehicleType">
            차량 종류
          </label>

          <select
            id="vehicleType"
            value={vehicleType}
            onChange={(event) =>
              setVehicleType(
                event.target.value
              )
            }
          >
            <option value="small-truck">
              소형 화물차
            </option>

            <option value="van">
              승합차
            </option>

            <option value="motorcycle">
              이륜차
            </option>
          </select>
        </div>

        <div>
          <label htmlFor="departureTime">
            출발 예정 시각
          </label>

          <input
            id="departureTime"
            type="time"
            value={departureTime}
            onChange={(event) =>
              setDepartureTime(
                event.target.value
              )
            }
          />
        </div>

        <button
          className="full-width-button"
          type="submit"
          disabled={isLoading}
        >
          추천 경로 찾기
        </button>
      </form>
    </main>
  );
}

export default InputPage;