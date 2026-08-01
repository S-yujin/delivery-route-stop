import { API_BASE_URL } from "../config/apiConfig";

async function requestApi(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      `API 요청 실패: ${response.status} ${errorText}`
    );
  }

  return response.json();
}

export async function geocodeAddress(address) {
  return requestApi("/api/routes/geocode", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      address,
    }),
  });
}

export async function optimizeRoute(requestData) {
  return requestApi("/api/routes/optimize", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestData),
  });
}

export async function getDirections(start, goal) {
  return requestApi("/api/routes/directions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      start: {
        longitude: start.longitude,
        latitude: start.latitude,
      },
      goal: {
        longitude: goal.longitude,
        latitude: goal.latitude,
      },
    }),
  });
}

/* ===========================
   추가
=========================== */

export async function getNextStop(requestData) {
  return requestApi("/api/routes/next-stop", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestData),
  });
}