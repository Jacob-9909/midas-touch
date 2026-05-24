"""CLI orchestration script for running the Market Data Pipeline and saving to Azure SQL.

Usage:
    uv run scripts/run_market_pipeline.py --start 2026-05-01 --end 2026-05-24
    uv run scripts/run_market_pipeline.py --backfill --start 2026-01-01
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from collections import Counter

# Set up project root and source path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from db.connector import bulk_upsert_market_snapshots
from data_pipeline.fetch_market_data import MarketDataPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Midas Touch 시장 데이터 수집 및 Azure SQL 적재 파이프라인")
    parser.add_argument(
        "--start",
        help="수집 시작일 (YYYY-MM-DD) [기본값: 7일 전]",
    )
    parser.add_argument(
        "--end",
        help="수집 종료일 (YYYY-MM-DD) [기본값: 오늘]",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="대용량 백필 실행 활성화 (기본 90일 전부터 수집)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="SQL Server 적재 배치 크기 (기본값: 100)",
    )
    args = parser.parse_args()

    # Determine date range
    today = datetime.now()
    if args.end:
        end_dt = datetime.strptime(args.end, "%Y-%m-%d")
    else:
        end_dt = today

    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        if args.backfill:
            # 90 days of history for backfill
            start_dt = end_dt - timedelta(days=90)
        else:
            # Default to 7 days
            start_dt = end_dt - timedelta(days=7)

    # Format as string
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    print("=" * 60)
    print("           MIDAS TOUCH MARKET DATA INGESTION PIPELINE")
    print("=" * 60)
    print(f"수집 기간: {start_str} ~ {end_str}")
    print(f"모드     : {'백필(Backfill)' if args.backfill else '일반 배치(Daily)'}")
    print(f"배치 크기: {args.batch_size}")
    print("-" * 60)

    # 1. Fetching
    print("1. 외부 API 데이터 수집을 시작합니다...")
    pipeline = MarketDataPipeline()
    snapshots = pipeline.fetch_all(start_str, end_str)
    
    total_records = len(snapshots)
    print(f"\n수집 완료: 총 {total_records:,}개의 데이터 레코드 획득.")
    
    if total_records == 0:
        print("수집된 레코드가 없어 작업을 조기 종료합니다.")
        return

    # Aggregate stats
    stats = Counter()
    for snap in snapshots:
        key = f"{snap['data_type']} ({snap['sub_key']}) [Source: {snap['source']}]"
        stats[key] += 1
        
    print("\n[수집 요약]")
    for key, count in stats.most_common():
        print(f" - {key}: {count:,} 건")
    print("-" * 60)

    # 2. Saving to Azure SQL
    print("2. Azure SQL Database 적재를 시작합니다...")
    saved_count = 0
    
    # Save in batches
    for i in range(0, total_records, args.batch_size):
        batch = snapshots[i : i + args.batch_size]
        try:
            count = bulk_upsert_market_snapshots(batch)
            saved_count += count
            print(f" - [적재 진행] {saved_count:,} / {total_records:,} 레코드 완료")
        except Exception as e:
            print(f"⚠️ [오류 발생] 적재 중 예외 발생 (인덱스 {i}): {e}")
            print("다음 배치 적재를 지속합니다...")

    print("=" * 60)
    print(f"🎉 파이프라인 실행 완료! ({saved_count:,} / {total_records:,} 건 적재 성공)")
    print("=" * 60)


if __name__ == "__main__":
    main()
