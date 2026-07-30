export const mockRouteResponse = {
  summary: {
    totalDistanceKm: 8.3,
    estimatedTimeMinutes: 42,
    savedTimeMinutes: 11,
    candidateCount: 2,
  },

  routeOrder: [
    {
      id: "S1",
      type: "start",
      order: 0,
      name: "출발지",
      address: "대전광역시 동구 중앙로 215",
      latitude: 36.332,
      longitude: 127.434,
    },
    {
      id: "D1",
      type: "destination",
      order: 1,
      name: "배송지 1",
      address: "대전광역시 서구 둔산로 100",
      latitude: 36.3504,
      longitude: 127.3845,
    },
  ],

  stopCandidates: [
    {
      id: "P1",
      type: "stop",
      destinationId: "D1",
      name: "정차 후보지 A",
      address: "대전광역시 서구 둔산로 인근",
      latitude: 36.354,
      longitude: 127.389,
      score: 82,
      walkingDistance: 60,
      reason: "배송지와 가깝지만 교통량이 다소 많습니다.",
    },
    {
      id: "P2",
      type: "stop",
      destinationId: "D1",
      name: "정차 후보지 B",
      address: "대전광역시 서구 시청로 인근",
      latitude: 36.3465,
      longitude: 127.3795,
      score: 91,
      walkingDistance: 180,
      reason: "도보 거리는 길지만 정차 여건이 좋습니다.",
    },
  ],

  path: [],
};