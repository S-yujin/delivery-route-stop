import { useEffect, useRef, useState } from "react";
import { loadNaverMap } from "../utils/loadNaverMap";
import { mockLocations } from "../data/mockLocations";
import LocationCard from "./LocationCard";

const defaultCenter = {
  latitude: 36.3504,
  longitude: 127.3845,
};

function MapView() {
  const mapElement = useRef(null);
  const mapInstance = useRef(null);
  const markerInstances = useRef([]);

  const [selectedId, setSelectedId] = useState("P1");

  const stopLocations = mockLocations.filter(
    (location) => location.type === "stop"
  );

  const selectedLocation = mockLocations.find(
    (location) => location.id === selectedId
  );

  useEffect(() => {
    let isMounted = true;

    async function initializeMap() {
      try {
        const naver = await loadNaverMap();

        if (!isMounted || !mapElement.current || mapInstance.current) {
          return;
        }

        const center = new naver.maps.LatLng(
          defaultCenter.latitude,
          defaultCenter.longitude
        );

        mapInstance.current = new naver.maps.Map(mapElement.current, {
          center,
          zoom: 14,
          zoomControl: true,
          zoomControlOptions: {
            position: naver.maps.Position.TOP_RIGHT,
          },
        });

        markerInstances.current = mockLocations.map((location) => {
          const position = new naver.maps.LatLng(
            location.latitude,
            location.longitude
          );

          const marker = new naver.maps.Marker({
            position,
            map: mapInstance.current,
            title: location.name,
          });

          naver.maps.Event.addListener(marker, "click", () => {
            setSelectedId(location.id);
            mapInstance.current.panTo(position);
          });

          return marker;
        });

        const bounds = new naver.maps.LatLngBounds();

        mockLocations.forEach((location) => {
          bounds.extend(
            new naver.maps.LatLng(
              location.latitude,
              location.longitude
            )
          );
        });

        mapInstance.current.fitBounds(bounds);
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

      if (mapInstance.current) {
        mapInstance.current.destroy();
        mapInstance.current = null;
      }
    };
  }, []);

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
        <h2>추천 정차 후보지</h2>

        <div className="location-list">
          {stopLocations.map((location) => (
            <LocationCard
              key={location.id}
              location={location}
              selected={selectedId === location.id}
              onClick={() => handleLocationClick(location)}
            />
          ))}
        </div>

        {selectedLocation && (
          <div className="selected-location">
            <h3>{selectedLocation.name}</h3>
            <p>{selectedLocation.address}</p>

            {selectedLocation.score !== undefined && (
              <p>
                하역 적합도:{" "}
                <strong>{selectedLocation.score}점</strong>
              </p>
            )}

            {selectedLocation.walkingDistance !== undefined && (
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