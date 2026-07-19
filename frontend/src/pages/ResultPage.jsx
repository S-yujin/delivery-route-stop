import { useLocation, useNavigate } from "react-router-dom";
import MapView from "../components/MapView";

function ResultPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const inputData = location.state;

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

  const {
    start,
    destinations,
    vehicleType,
    departureTime,
  } = inputData;

  const vehicleLabels = {
    "small-truck": "소형 화물차",
    van: "승합차",
    motorcycle: "이륜차",
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
          <strong>{vehicleLabels[vehicleType]}</strong>
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

      <section>
        <h2>배송 경로 지도</h2>
        <MapView />
      </section>
    </main>
  );
}

export default ResultPage;