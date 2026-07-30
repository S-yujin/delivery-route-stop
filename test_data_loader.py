from backend.services.data_loader import (
    load_delivery_allowed_segments,
)


def main() -> None:
    segments = load_delivery_allowed_segments()

    print(f"전체 허용구간 수: {len(segments)}")
    print()

    for index, segment in enumerate(segments[:5], start=1):
        print(f"[허용구간 {index}]")
        print(f"구간 ID: {segment['segment_id']}")
        print(f"시점: {segment['start_point']}")
        print(f"종점: {segment['end_point']}")
        print(f"구간 길이: {segment['length_km']} km")
        print(f"허용구분: {segment['allowed_type']}")
        print(f"원본 허용시간: {segment['allowed_time_text']}")
        print(f"허용 시작시간: {segment['allowed_start_time']}")
        print(f"허용 종료시간: {segment['allowed_end_time']}")
        print(f"최대 정차시간: {segment['max_stop_minutes']}분")
        print(f"허용일자: {segment['allowed_date']}")
        print("-" * 50)


if __name__ == "__main__":
    main()