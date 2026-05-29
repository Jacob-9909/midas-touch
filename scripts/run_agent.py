"""CLI orchestration script to run the Midas Touch RAG adviser agent.

Usage:
    uv run scripts/run_agent.py --query "30대 대기업 대리, 부동산 청약 준비 중..."
    uv run scripts/run_agent.py --interactive
"""

import argparse
import os
import sys

# Set up project root and source path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.recommender import MidasAdviser


def print_banner() -> None:
    print("=" * 70)
    print("        🤖 MIDAS TOUCH HYPER-PERSONALIZED FINANCIAL RECOMMENDATION AGENT")
    print("=" * 70)


def interactive_mode() -> str:
    print("\n[대화형 모드] 의뢰인의 프로필 및 자산 현황을 입력받아 추천서를 생성합니다.")
    print("-" * 70)
    
    age = input("1. 나이를 입력해 주세요 (예: 34): ").strip()
    occupation = input("2. 직업 및 회사 구분을 입력해 주세요 (예: IT 기업 개발자): ").strip()
    income = input("3. 가구당 세전 월 소득을 입력해 주세요 (예: 500만원): ").strip()
    asset_goals = input("4. 주요 투자 목적 및 현재 고민을 입력해 주세요\n   (예: 3년 내 자녀 교육자금 및 마포구 청약 계약금 마련): ").strip()
    propensity = input("5. 투자 선호 성향을 선택/입력해 주세요\n   (안전형 / 중위험-중수익 / 적극투자형 / 기타 구체적 서술): ").strip()

    # Construct unified query
    parts = []
    if age:
        parts.append(f"나이는 {age}세입니다.")
    if occupation:
        parts.append(f"직업은 {occupation}입니다.")
    if income:
        parts.append(f"월 소득은 {income}입니다.")
    if asset_goals:
        parts.append(f"투자 목표 및 고민사항은 '{asset_goals}' 입니다.")
    if propensity:
        parts.append(f"선호 투자 성향은 '{propensity}' 성향입니다.")
        
    query = " ".join(parts)
    print("-" * 70)
    print(f"생성된 의뢰 프로필 쿼리:\n>> {query}")
    return query


def main() -> None:
    print_banner()

    parser = argparse.ArgumentParser(description="Midas Touch RAG 기반 초개인화 포트폴리오 자문 엔진")
    parser.add_argument(
        "--query", "-q",
        help="의뢰 고객의 인적/금융 성향 텍스트 정보 (제공하지 않으면 대화형 입력 모드로 전환)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="대화형 질문 모드로 실행",
    )
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=3,
        help="Supabase pgvector에서 매칭할 유사 투자자 수 (기본값: 3)",
    )
    parser.add_argument(
        "--output", "-o",
        help="생성된 포트폴리오 추천 제안서 마크다운 파일 저장 경로",
    )
    args = parser.parse_args()

    # Determine query
    if args.interactive or not args.query:
        query = interactive_mode()
    else:
        query = args.query

    if not query.strip():
        print("❌ 오류: 입력 쿼리가 빈 값입니다. 프로그램을 종료합니다.")
        sys.exit(1)

    # Validate NVIDIA API Key
    if not os.environ.get("NVIDIA_API_KEY"):
        print("❌ 오류: NVIDIA_API_KEY 환경변수가 설정되어 있지 않습니다.")
        print("   .env 파일에 API 키가 정상적으로 설정되어 있는지 확인해 주세요.")
        sys.exit(1)

    try:
        # Initialize agent
        adviser = MidasAdviser()
        
        # Get recommendation report
        report = adviser.get_recommendation(query, top_k=args.top_k)

        # Output logic
        print("\n" + "=" * 70)
        print("           📜 MIDAS TOUCH 초개인화 자산관리 보고서 (RECOMMENDATION REPORT)")
        print("=" * 70)
        print(report)
        print("=" * 70 + "\n")

        # Save to file if specified
        if args.output:
            out_path = args.output
            # If path doesn't have markdown extension, append it
            if not out_path.endswith(".md"):
                out_path += ".md"
            
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"🎉 제안서 보고서가 파일로 저장되었습니다: {out_path}")

    except Exception as e:
        print(f"\n❌ 에이전트 추천 과정 중 심각한 에러 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
