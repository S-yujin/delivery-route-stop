from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
from geopandas import GeoDataFrame


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SHP_DIR = DATA_DIR / "parking_allowed_shp"

TARGET_CRS = "EPSG:4326"


def find_shapefile() -> Path:
    if not SHP_DIR.exists():
        raise FileNotFoundError(
            f"SHP 폴더를 찾을 수 없습니다: {SHP_DIR}\n"
            "data/parking_allowed_shp 폴더를 만들고 "
            ".shp, .shx, .dbf, .prj, .cpg 파일을 넣어주세요."
        )

    shapefiles = sorted(SHP_DIR.glob("*.shp"))

    if not shapefiles:
        raise FileNotFoundError(
            f"SHP 파일을 찾을 수 없습니다: {SHP_DIR}"
        )

    return shapefiles[0]


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in {
        "",
        "nan",
        "none",
        "null",
        "nat",
    }:
        return ""

    return text


def normalize_column_name(column_name: Any) -> str:
    return clean_text(column_name)


def normalize_columns(gdf: GeoDataFrame) -> GeoDataFrame:
    copied = gdf.copy()

    copied.columns = [
        normalize_column_name(column)
        for column in copied.columns
    ]

    return copied


def read_shapefile(shp_path: Path) -> GeoDataFrame:
    try:
        return gpd.read_file(
            shp_path,
            engine="pyogrio",
        )

    except Exception as pyogrio_error:
        print(
            "[경고] pyogrio로 SHP를 읽지 못했습니다. "
            "기본 엔진으로 다시 시도합니다."
        )
        print(f"[pyogrio 오류] {pyogrio_error}")

        try:
            return gpd.read_file(shp_path)

        except Exception as fallback_error:
            raise RuntimeError(
                "SHP 파일을 읽는 데 실패했습니다.\n"
                f"파일: {shp_path}\n"
                f"오류: {fallback_error}"
            ) from fallback_error


def ensure_coordinate_system(
    gdf: GeoDataFrame,
) -> GeoDataFrame:
    if gdf.crs is None:
        raise ValueError(
            "SHP 파일에 좌표계 정보가 없습니다. "
            ".prj 파일이 함께 있는지 확인해주세요."
        )

    if gdf.crs.to_string().upper() != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)

    return gdf


def remove_invalid_geometry(
    gdf: GeoDataFrame,
) -> GeoDataFrame:
    cleaned = gdf.copy()

    cleaned = cleaned[
        cleaned.geometry.notna()
    ]

    cleaned = cleaned[
        ~cleaned.geometry.is_empty
    ]

    cleaned = cleaned.reset_index(drop=True)

    return cleaned


def filter_line_geometry(
    gdf: GeoDataFrame,
) -> GeoDataFrame:
    allowed_types = {
        "LineString",
        "MultiLineString",
    }

    filtered = gdf[
        gdf.geometry.geom_type.isin(allowed_types)
    ].copy()

    filtered = filtered.reset_index(drop=True)

    return filtered


def remove_duplicate_geometry(
    gdf: GeoDataFrame,
) -> GeoDataFrame:
    copied = gdf.copy()

    copied["_geometry_wkb"] = copied.geometry.apply(
        lambda geometry: geometry.wkb_hex
    )

    copied = copied.drop_duplicates(
        subset=["_geometry_wkb"]
    )

    copied = copied.drop(
        columns=["_geometry_wkb"]
    )

    copied = copied.reset_index(drop=True)

    return copied


def get_column_value(
    row: Any,
    candidate_columns: list[str],
) -> str:
    for column_name in candidate_columns:
        if column_name in row.index:
            value = clean_text(row[column_name])

            if value:
                return value

    return ""


def normalize_segment_row(
    row: Any,
    index: int,
) -> dict[str, Any]:
    district = get_column_value(
        row,
        [
            "구",
            "자치구",
            "시군구",
            "구명",
            "SIGUNGU",
        ],
    )

    segment_name = get_column_value(
        row,
        [
            "구간",
            "구간명",
            "도로명",
            "노선명",
            "위치",
            "ROAD_NAME",
        ],
    )

    allowed_time = get_column_value(
        row,
        [
            "시간",
            "허용시간",
            "운영시간",
            "TIME",
        ],
    )

    category = get_column_value(
        row,
        [
            "용도",
            "허용용도",
            "주정차용도",
            "유형",
            "종류",
            "CATEGORY",
        ],
    )

    usage_code = get_column_value(
        row,
        [
            "구분",
            "구분코드",
            "유형코드",
        ],
    )

    code = get_column_value(
        row,
        [
            "코드",
            "구간코드",
            "관리번호",
            "CODE",
        ],
    )

    allowed_date = get_column_value(
        row,
        [
            "허용일",
            "허용날짜",
            "날짜",
            "DATE",
        ],
    )

    source_index = get_column_value(
        row,
        [
            "인덱스",
            "INDEX",
            "index",
        ],
    )

    geometry = row.geometry

    return {
        "segment_id": (
            source_index
            if source_index
            else str(index + 1)
        ),
        "district": district,
        "segment_name": segment_name,
        "allowed_time": allowed_time,
        "allowed_date": allowed_date,
        "category": category,
        "usage_code": usage_code,
        "code": code,
        "geometry_type": geometry.geom_type,
        "geometry": geometry,
    }


@lru_cache(maxsize=1)
def load_parking_allowed_geodataframe() -> GeoDataFrame:
    shp_path = find_shapefile()

    gdf = read_shapefile(shp_path)

    if gdf.empty:
        raise ValueError(
            f"SHP 파일에 데이터가 없습니다: {shp_path}"
        )

    gdf = normalize_columns(gdf)
    gdf = ensure_coordinate_system(gdf)
    gdf = remove_invalid_geometry(gdf)
    gdf = filter_line_geometry(gdf)
    gdf = remove_duplicate_geometry(gdf)

    if gdf.empty:
        raise ValueError(
            "유효한 LineString 또는 MultiLineString "
            "데이터가 없습니다."
        )

    return gdf


@lru_cache(maxsize=1)
def load_parking_allowed_segments() -> list[dict[str, Any]]:
    gdf = load_parking_allowed_geodataframe()

    segments: list[dict[str, Any]] = []

    for index, row in gdf.iterrows():
        segment = normalize_segment_row(
            row=row,
            index=index,
        )

        segments.append(segment)

    return segments


def clear_spatial_data_cache() -> None:
    load_parking_allowed_geodataframe.cache_clear()
    load_parking_allowed_segments.cache_clear()


def print_shapefile_summary() -> None:
    shp_path = find_shapefile()
    gdf = load_parking_allowed_geodataframe()

    print("=" * 60)
    print("대전광역시 주정차 허용구간 SHP 로딩 결과")
    print("=" * 60)

    print(f"SHP 파일: {shp_path}")
    print(f"전체 레코드 수: {len(gdf)}")
    print(f"좌표계: {gdf.crs}")

    print("\n컬럼 목록:")

    for column in gdf.columns:
        print(f"- {column}")

    print("\nGeometry 유형:")

    geometry_counts = (
        gdf.geometry.geom_type
        .value_counts()
        .to_dict()
    )

    for geometry_type, count in geometry_counts.items():
        print(f"- {geometry_type}: {count}개")

    print("\n전체 공간 범위:")

    min_x, min_y, max_x, max_y = gdf.total_bounds

    print(f"- 최소 경도: {min_x}")
    print(f"- 최소 위도: {min_y}")
    print(f"- 최대 경도: {max_x}")
    print(f"- 최대 위도: {max_y}")

    print("\n첫 번째 데이터 속성:")

    first_row = gdf.iloc[0]

    for column in gdf.columns:
        if column == "geometry":
            print(
                f"- geometry: "
                f"{first_row.geometry.geom_type}"
            )
        else:
            print(
                f"- {column}: "
                f"{clean_text(first_row[column])}"
            )

    print("\n정규화된 데이터 예시:")

    segments = load_parking_allowed_segments()

    for segment in segments[:3]:
        printable_segment = {
            key: value
            for key, value in segment.items()
            if key != "geometry"
        }

        print(printable_segment)

    print("=" * 60)


if __name__ == "__main__":
    try:
        print_shapefile_summary()

    except Exception as error:
        print("[SHP 로딩 실패]")
        print(error)
        raise