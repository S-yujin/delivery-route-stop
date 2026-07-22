const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!apiBaseUrl) {
  throw new Error(
    "VITE_API_BASE_URL이 설정되지 않았습니다. frontend/.env 파일을 확인하세요."
  );
}

export const API_BASE_URL = apiBaseUrl;