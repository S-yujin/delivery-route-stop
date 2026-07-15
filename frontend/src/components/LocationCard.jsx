function LocationCard({ location, selected, onClick }) {
  return (
    <button
      type="button"
      className={`location-card ${selected ? "selected" : ""}`}
      onClick={onClick}
    >
      <div className="location-card-header">
        <strong>{location.name}</strong>

        {location.score !== undefined && (
          <span className="score">{location.score}점</span>
        )}
      </div>

      <span>{location.address}</span>

      {location.walkingDistance !== undefined && (
        <span>도보 거리: {location.walkingDistance}m</span>
      )}

      {location.reason && (
        <span className="location-reason">{location.reason}</span>
      )}
    </button>
  );
}

export default LocationCard;