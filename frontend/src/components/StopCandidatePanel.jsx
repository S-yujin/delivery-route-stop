import { useState } from "react";

function StopCandidatePanel({
  stopCandidates = [],
}) {
  const [sortType, setSortType] =
    useState("score");

  const [selectedId, setSelectedId] =
    useState(null);

  const sortedCandidates = [
    ...stopCandidates,
  ].sort((a, b) => {
    if (sortType === "distance") {
      return (
        Number(a.walkingDistance ?? 0) -
        Number(b.walkingDistance ?? 0)
      );
    }

    return (
      Number(b.score ?? 0) -
      Number(a.score ?? 0)
    );
  });

  const selectedCandidate =
    sortedCandidates.find(
      (candidate) =>
        candidate.id === selectedId
    ) ?? null;

  return (
    <section className="stop-candidate-section">
      <div className="section-heading candidate-heading">
        <div>
          <h2>추천 정차 후보지</h2>
          <p>
            배송지 주변에서 조건을 통과한 정차
            후보입니다.
          </p>
        </div>

        <select
          className="candidate-sort-select"
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

      {sortedCandidates.length === 0 ? (
        <div className="empty-candidates">
          <strong>
            추천 가능한 정차 후보지가 없습니다.
          </strong>

          <p>
            검색 조건을 변경하거나 잠시 후 다시
            시도해 주세요.
          </p>

          <button
            className="secondary-button"
            type="button"
            onClick={() =>
              window.location.reload()
            }
          >
            다시 시도
          </button>
        </div>
      ) : (
        <div className="stop-candidate-list">
          {sortedCandidates.map(
            (candidate, index) => {
              const isSelected =
                candidate.id === selectedId;

              return (
                <button
                  className={`stop-candidate-card ${
                    isSelected
                      ? "selected"
                      : ""
                  }`}
                  type="button"
                  key={candidate.id}
                  onClick={() =>
                    setSelectedId(
                      isSelected
                        ? null
                        : candidate.id
                    )
                  }
                >
                  <div className="candidate-card-header">
                    <span className="candidate-rank">
                      {candidate.rank ??
                        index + 1}
                    </span>

                    <div>
                      <strong>
                        {candidate.name ??
                          "정차 후보지"}
                      </strong>

                      <p>
                        {candidate.address ??
                          `배송지 ${candidate.destinationId}`}
                      </p>
                    </div>

                    <span className="candidate-score">
                      {Math.round(
                        candidate.score ?? 0
                      )}
                      점
                    </span>
                  </div>

                  <div className="candidate-card-info">
                    <span>
                      도보{" "}
                      {candidate.walkingDistance ??
                        "-"}
                      m
                    </span>

                    <span>
                      약{" "}
                      {candidate.walkingTime ??
                        "-"}
                      분
                    </span>

                    {candidate.maxStopMinutes && (
                      <span>
                        최대{" "}
                        {
                          candidate.maxStopMinutes
                        }
                        분
                      </span>
                    )}
                  </div>

                  {candidate.type ===
                    "selected-stop" && (
                    <span className="selected-stop-label">
                      최종 추천 정차지
                    </span>
                  )}
                </button>
              );
            }
          )}
        </div>
      )}

      {selectedCandidate && (
        <div className="selected-candidate-summary">
          <strong>
            {selectedCandidate.name ??
              "선택한 정차 후보지"}
          </strong>

          <p>
            {selectedCandidate.reason ??
              "정차 후보지의 상세 정보입니다."}
          </p>
        </div>
      )}
    </section>
  );
}

export default StopCandidatePanel;