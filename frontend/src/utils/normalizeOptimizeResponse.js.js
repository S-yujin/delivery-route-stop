export function normalizeOptimizeResponse(
    response,
    request
) {
    const destinationMap = new Map(
        request.destinations.map((destination) => [
            destination.id,
            destination,
        ])
    );

    const candidateMap = new Map(
        request.stop_candidates.map((candidate)=>[
            candidate.id,
            candidate,
        ])
    );

    const routeOrder =
        response.recommended_delivery_order.map(
            (item)=>{
                const destination =
                    destinationMap.get(t=item.destination_id);
                
                return {
                    id: item.destination_id,
                    type: "destination",
                    order: item.order,
                    name:
                    item.destination_name ??
                    destination?.name ??
                    '배송지 ${item.order}',
                    address: destination?.address ?? "",
                    latitude: destination?.latitude,
                    longitude: destination?.longitude,
                    distanceMeters: item.distance_m,
                    distanceKm: item.distance_km,
                    deliveryCount: item.delivery_count,
                };
            }
        );


        const stopCandidates = response.candidate_results.map((item)=>{
            const candidate =
                candidateMap.get(item.candidate_id);

            return {
                id: item.candidate_id,
                type: "stop",
                destinationId: 
                    candidate?.destination_id ?? null,
                 name: 
                    item.candidate_name ??
                    candidate?.name ??
                    "정차 후보지",
                address: candidate?.daaress ?? "",
                latitude: candidate?.latitude,
                longitude: candidate?.longitude,

                parkingAvailable:
                    item.parking_available,
                maxStopMinutes:
                    item.max_stop_minutes,
                roadWidthScore:
                    item.road_width_score,
        s       safetyScore:
                    item.safety_score,

                walkingDistance:
                    item.total_distance_m,

                score:
                Number(item.road_width_score ?? 0) +
                Number(item.safety_score ?? 0) +
                (item.parking_available ? 20 : 0),

                elected:
                    item.candidate_id ===
                    response.selected_stop?.id,

                reason:
                    item.candidate_id ===
                    response.selected_stop?.id
                    ? "현재 추천 알고리즘이 선택한 정차 후보지입니다."
                    : "추천 후보 비교 결과에 포함된 정차 위치입니다.",
            };
        });

        return{
            summary: {
                totalDistanceKm:
                    response.total_distance_km ?? 0,
                estimatedTimeMinutes:
                    response.total_service_time_minutes ?? 0,
                savedTimeMinutes: 0,
                candidateCount: stopCandidates.length,
        },

        routeOrder,
        stopCandidates,
        path: [],

        calculationMethod:
          response.calculation_method ?? "",

        selectedStopId:
         response.selected_stop?.id ?? null,
  };
}