import { useState } from "react";
import { useNavigate } from "react-router-dom";

function InputPage() {
  const navigate = useNavigate();

  const [start, setStart] = useState("");
  const [destinations, setDestinations] = useState([""]);
  const [vehicleType, setVehicleType] = useState("small-truck");
  const [departureTime, setDepartureTime] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleDestinationChange = (index, value) => {
    const updatedDestinations = [...destinations];
    updatedDestinations[index] = value;
    setDestinations(updatedDestinations);
  };

  const handleAddDestination = () => {
    setDestinations([...destinations, ""]);
  };

  const handleRemoveDestination = (index) => {
    if (destinations.length === 1) {
      return;
    }

    const updatedDestinations = destinations.filter(
      (_, destinationIndex) => destinationIndex !== index
    );

    setDestinations(updatedDestinations);
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    const validDestinations = destinations.filter(
      (destination) => destination.trim() !== ""
    );

    if (start.trim() === "") {
      alert("출발지를 입력해주세요.");
      return;
    }

    if (validDestinations.length === 0) {
      alert("배송지를 한 곳 이상 입력해주세요.");
      return;
    }

    setIsLoading(true);

    setTimeout(() => {
      navigate("/result", {
        state: {
          start,
          destinations: validDestinations,
          vehicleType,
          departureTime,
        },
      });
    }, 1000);
  };

  if (isLoading) {
    return (
      <main>
        <div className="loading-screen">
          <div className="loading-spinner" />
          <h1>추천 경로를 분석 중입니다.</h1>
          <p>배송 순서와 정차 후보지를 계산하고 있습니다.</p>
        </div>
      </main>
    );
  }

  return (
    <main>
      <header className="input-header">
        <h1>CurbRoute AI</h1>
        <p>배송 경로와 안전한 하역 정차 위치를 추천합니다.</p>
      </header>

      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="start">출발지</label>
          <input
            id="start"
            type="text"
            value={start}
            onChange={(event) => setStart(event.target.value)}
            placeholder="예: 대전역"
          />
        </div>

        <section className="destination-section">
          <div className="section-title-row">
            <label>배송지</label>

            <button
              type="button"
              className="add-destination-button"
              onClick={handleAddDestination}
            >
              + 배송지 추가
            </button>
          </div>

          <div className="destination-list">
            {destinations.map((destination, index) => (
              <div className="destination-row" key={index}>
                <span className="destination-number">{index + 1}</span>

                <input
                  type="text"
                  value={destination}
                  onChange={(event) =>
                    handleDestinationChange(index, event.target.value)
                  }
                  placeholder={`배송지 ${index + 1} 주소`}
                />

                <button
                  type="button"
                  className="remove-destination-button"
                  onClick={() => handleRemoveDestination(index)}
                  disabled={destinations.length === 1}
                  aria-label={`배송지 ${index + 1} 삭제`}
                >
                  삭제
                </button>
              </div>
            ))}
          </div>
        </section>

        <div>
          <label htmlFor="vehicleType">차량 종류</label>
          <select
            id="vehicleType"
            value={vehicleType}
            onChange={(event) => setVehicleType(event.target.value)}
          >
            <option value="small-truck">소형 화물차</option>
            <option value="van">승합차</option>
            <option value="motorcycle">이륜차</option>
          </select>
        </div>

        <div>
          <label htmlFor="departureTime">출발 예정 시각</label>
          <input
            id="departureTime"
            type="time"
            value={departureTime}
            onChange={(event) => setDepartureTime(event.target.value)}
          />
        </div>

        <button className="full-width-button" type="submit">
          추천 경로 찾기
        </button>
      </form>
    </main>
  );
}

export default InputPage;