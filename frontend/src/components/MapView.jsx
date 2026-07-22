import { useEffect, useRef, useState } from "react";
import { loadNaverMap } from "../utils/loadNaverMap";
import { mockLocations } from "../data/mockLocations";
import LocationCard from "./LocationCard";

const defaultCenter = {
  latitude: 36.3504,
  longitude: 127.3845,
};

function getMarkerContent(location) {
  if (location.type === "start") {
    return `
      <div class="custom-marker marker-start">
        <span>출발</span>
      </div>
    `;
  }

  if (location.type === "destination") {
    return `
      <div class="custom-marker marker-destination">
        <span>${location.order ?? ""}</span>
      </div>
    `;
  }

  return `
    <div class="custom-marker marker-stop">
      <span>P</span>
    </div>
  `;
}

function MapView({
  startLocation,
  destinationLocations = [],
}) {
  const mapElement = useRef(null);
  const mapInstance = useRef(null);
  const markerInstances = useRef([]);
  const polylineInstance = useRef(null);

  const [selectedId, setSelectedId] = useState("P1");
  const [sortType, setSortType] = useState("score");

  const routeLocations = [
    startLocation,
    ...destinationLocations,
  ].filter(Boolean);

  const stopLocations = [...mockLocations]
    .filter((location) => location.type === "stop")
    .sort((a, b) => {
      if (sortType === "distance") {
        return (
          Number(a.walkingDistance) -
          Number(b.walkingDistance)
        );
      }

      return Number(b.score) - Number(a.score);
    });

  const selectedLocation = stopLocations.find(
    (location) => location.id === selectedId
  );

  const allLocations=[
    ...routeLocations,
    ...stopLocations,
  ];

  useEffect(() => {
    let isMounted = true;

    async function initializeMap() {
      try {
        const naver = await loadNaverMap();

        if (
          !isMounted ||
          !mapElement.current ||
          mapInstance.current
        ) {
          return;
        }

        const center = new naver.maps.LatLng(
          defaultCenter.latitude,
          defaultCenter.longitude
        );

        mapInstance.current = new naver.maps.Map(
          mapElement.current,
          {
            center,
            zoom: 14,
            zoomControl: true,
            zoomControlOptions: {
              position: naver.maps.Position.TOP_RIGHT,
            },
          }
        );

        markerInstances.current = allLocations.map(
          (location) => {
            const position = new naver.maps.LatLng(
              location.latitude,
              location.longitude
            );

            const marker = new naver.maps.Marker({
              position,
              map: mapInstance.current,
              title: location.name,
              icon: {
                content: getMarkerContent(location),
                anchor: new naver.maps.Point(20, 42),
              },
            });

            naver.maps.Event.addListener(
              marker,
              "click",
              () => {
                setSelectedId(location.id);
                mapInstance.current.panTo(position);
              }
            );

            return marker;
          }
        );

        const bounds = new naver.maps.LatLngBounds();

        allLocations.forEach((location) => {
          bounds.extend(
            new naver.maps.LatLng(
              location.latitude,
              location.longitude
            )
          );
        });

        mapInstance.current.fitBounds(bounds);

        const routePath = routeLocations.map(
          (location) =>
            new naver.maps.LatLng(
              location.latitude,
              location.longitude
            )
        );

        polylineInstance.current =
          new naver.maps.Polyline({
            map: mapInstance.current,
            path: routePath,
            strokeWeight: 5,
            strokeOpacity: 0.85,
            strokeLineCap: "round",
            strokeLineJoin: "round",
          });
      } catch (error) {
        console.error(error);
      }
    }

    initializeMap();

    return () => {
      isMounted = false;

      markerInstances.current.forEach((marker) => {
        marker.setMap(null);
      });

      markerInstances.current = [];

      if (polylineInstance.current) {
        polylineInstance.current.setMap(null);
        polylineInstance.current = null;
      }

      if (mapInstance.current) {
        mapInstance.current.destroy();
        mapInstance.current = null;
      }
    };
  }, [startLocation, destinationLocations]);

  const handleLocationClick = (location) => {
    setSelectedId(location.id);

    if (!mapInstance.current || !window.naver?.maps) {
      return;
    }

    const position = new window.naver.maps.LatLng(
      location.latitude,
      location.longitude
    );

    mapInstance.current.panTo(position);
    mapInstance.current.setZoom(17);
  };

  return (
    <section className="map-layout">
      <div ref={mapElement} className="naver-map" />

      <aside className="location-sidebar">
        <div className="candidate-header">
          <h2>추천 정차 후보지</h2>

          <select
            className="candidate-sort"
            value={sortType}
            onChange={(event) =>
              setSortType(event.target.value)
            }
          >
            <option value="score">
              점수 높은 순
            </option>
            <option value="distance">
              도보 거리 짧은 순
            </option>
          </select>
        </div>

        {stopLocations.length > 0 ? (
          <div className="location-list">
            {stopLocations.map((location) => (
              <LocationCard
                key={location.id}
                location={location}
                selected={selectedId === location.id}
                onClick={() =>
                  handleLocationClick(location)
                }
              />
            ))}
          </div>
        ) : (
          <div className="empty-candidates">
            <strong>
              추천 가능한 정차 후보지가 없습니다.
            </strong>

            <p>
              검색 조건을 변경하거나 잠시 후 다시
              시도해 주세요.
            </p>

            <button
              type="button"
              className="retry-button"
              onClick={() => window.location.reload()}
            >
              다시 시도
            </button>
          </div>
        )}

        {stopLocations.length > 0 &&
          selectedLocation && (
            <div className="selected-location">
              <h3>{selectedLocation.name}</h3>
              <p>{selectedLocation.address}</p>

              {selectedLocation.score !== undefined && (
                <p>
                  하역 적합도:{" "}
                  <strong>
                    {selectedLocation.score}점
                  </strong>
                </p>
              )}

              {selectedLocation.walkingDistance !==
                undefined && (
                <p>
                  배송지까지 도보 거리:{" "}
                  {selectedLocation.walkingDistance}m
                </p>
              )}

              {selectedLocation.reason && (
                <p>{selectedLocation.reason}</p>
              )}
            </div>
          )}
      </aside>
    </section>
  );
}

export default MapView;