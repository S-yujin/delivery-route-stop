import { useNavigate } from "react-router-dom";

function InputPage() {
  const navigate = useNavigate();

  const handleSubmit = (event) => {
    event.preventDefault();
    navigate("/result");
  };

  return (
    <main>
      <h1>CurbRoute AI</h1>
      <p>배송 경로와 안전한 하역 정차 위치를 추천합니다.</p>

      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="start">출발지</label>
          <input
            id="start"
            type="text"
            placeholder="출발지를 입력하세요"
          />
        </div>

        <div>
          <label htmlFor="destination">배송지</label>
          <input
            id="destination"
            type="text"
            placeholder="배송지를 입력하세요"
          />
        </div>

        <button type="submit">추천 결과 확인</button>
      </form>
    </main>
  );
}

export default InputPage;