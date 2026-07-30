import { mockRouteResponse } from "./mockRouteResponse";

export const mockLocations = [
  ...mockRouteResponse.routeOrder,
  ...mockRouteResponse.stopCandidates,
];