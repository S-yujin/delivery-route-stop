import { useNavigate } from "react-router-dom";
import MapView from "../components/MapView";

function ResultPage() {
  const navigate = useNavigate();

  return (
    <main>
      <div className="page-header">
        <div>
          <h1>추천 결과</h1>
          <p>배송지 주변의 하역 정차 후보지를 확인하세요.</p>
        </div>

        <button type="button" onClick={() => navigate("/")}>
          다시 입력하기
        </button>
      </div>

      <section>
        <h2>배송 경로 지도</h2>
        <MapView />
      </section>

      <section>
        <h2>추천 정차 후보지</h2>
        <p>추천 후보지 정보가 이곳에 표시됩니다.</p>
      </section>
    </main>
  );
}

export default ResultPage;