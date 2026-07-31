import { useEffect, useRef } from "react";
import { loadNaverMap } from "../utils/loadNaverMap";

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

  if (location.type === "selected-stop") {
    return `
      <div class="custom-marker marker-selected-stop">
        <span>추천</span>
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
  directionsResult,
  stopCandidates = [],
}) {
  const mapElement = useRef(null);
  const mapInstance = useRef(null);
  const markerInstances = useRef([]);
  const polylineInstance = useRef(null);

  const routeLocations = [
    startLocation,
    ...destinationLocations,
  ].filter(Boolean);

  const stopLocations = [...stopCandidates];

  const allLocations = [
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
              position:
                naver.maps.Position.TOP_RIGHT,
            },
          }
        );

        markerInstances.current =
          allLocations.map((location) => {
            const position =
              new naver.maps.LatLng(
                location.latitude,
                location.longitude
              );

            const marker =
              new naver.maps.Marker({
                position,
                map: mapInstance.current,
                title:
                  location.name ??
                  location.address ??
                  "",
                icon: {
                  content:
                    getMarkerContent(location),
                  anchor:
                    new naver.maps.Point(
                      20,
                      42
                    ),
                },
              });

            naver.maps.Event.addListener(
              marker,
              "click",
              () => {
                mapInstance.current.panTo(
                  position
                );

                mapInstance.current.setZoom(
                  17
                );
              }
            );

            return marker;
          });

        if (allLocations.length > 0) {
          const bounds =
            new naver.maps.LatLngBounds();

          allLocations.forEach(
            (location) => {
              bounds.extend(
                new naver.maps.LatLng(
                  location.latitude,
                  location.longitude
                )
              );
            }
          );

          mapInstance.current.fitBounds(
            bounds
          );
        }

        const routePath =
          directionsResult?.path?.length > 0
            ? directionsResult.path.map(
                ([longitude, latitude]) =>
                  new naver.maps.LatLng(
                    latitude,
                    longitude
                  )
              )
            : routeLocations.map(
                (location) =>
                  new naver.maps.LatLng(
                    location.latitude,
                    location.longitude
                  )
              );

        if (routePath.length >= 2) {
          polylineInstance.current =
            new naver.maps.Polyline({
              map: mapInstance.current,
              path: routePath,
              strokeWeight: 5,
              strokeOpacity: 0.85,
              strokeLineCap: "round",
              strokeLineJoin: "round",
            });
        }
      } catch (error) {
        console.error(
          "네이버 지도 생성 실패:",
          error
        );
      }
    }

    initializeMap();

    return () => {
      isMounted = false;

      markerInstances.current.forEach(
        (marker) => {
          marker.setMap(null);
        }
      );

      markerInstances.current = [];

      if (polylineInstance.current) {
        polylineInstance.current.setMap(
          null
        );

        polylineInstance.current = null;
      }

      if (mapInstance.current) {
        mapInstance.current.destroy();
        mapInstance.current = null;
      }
    };
  }, [
    startLocation,
    destinationLocations,
    directionsResult,
    stopCandidates,
  ]);

  return (
    <div className="map-only-container">
      <div
        ref={mapElement}
        className="naver-map"
      />
    </div>
  );
}

export default MapView;