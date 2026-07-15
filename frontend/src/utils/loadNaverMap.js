let naverMapPromise = null;

export function loadNaverMap() {
  if (window.naver?.maps) {
    return Promise.resolve(window.naver);
  }

  if (naverMapPromise) {
    return naverMapPromise;
  }

  const clientId = import.meta.env.VITE_NAVER_MAP_CLIENT_ID;

  if (!clientId) {
    return Promise.reject(
      new Error("네이버 지도 Client ID가 설정되지 않았습니다.")
    );
  }

  naverMapPromise = new Promise((resolve, reject) => {
    const existingScript = document.querySelector(
      'script[data-naver-map="true"]'
    );

    if (existingScript) {
      existingScript.addEventListener("load", () => {
        resolve(window.naver);
      });

      existingScript.addEventListener("error", () => {
        reject(new Error("네이버 지도 로딩에 실패했습니다."));
      });

      return;
    }

    const script = document.createElement("script");

    script.src =
      `https://oapi.map.naver.com/openapi/v3/maps.js` +
      `?ncpKeyId=${clientId}`;

    script.async = true;
    script.dataset.naverMap = "true";

    script.onload = () => {
      if (window.naver?.maps) {
        resolve(window.naver);
      } else {
        reject(new Error("네이버 지도 객체를 찾지 못했습니다."));
      }
    };

    script.onerror = () => {
      reject(new Error("네이버 지도 스크립트 로딩에 실패했습니다."));
    };

    document.head.appendChild(script);
  });

  return naverMapPromise;
}