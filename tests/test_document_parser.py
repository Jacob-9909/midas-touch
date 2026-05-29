"""
tests/test_document_parser.py
------------------------------
통합 금융 문서 파서 및 Chunker 단위 테스트 (순수 assertion 활용).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.embedding_pipeline.config import DEFAULT_CONFIG
from src.embedding_pipeline.document_parser import DocumentParser, FinancialChunker


def test_financial_chunker():
    """FinancialChunker의 청킹 동작 및 오버랩 보존 테스트."""
    chunker = FinancialChunker(chunk_size=100, chunk_overlap=30)
    
    # 꽤 긴 금융 텍스트 예시 (한글 기준 약 200자)
    test_text = (
        "개인종합자산관리계좌(ISA)는 정부가 국민들의 자산 형성을 지원하기 위해 도입한 세제 혜택 상품입니다. "
        "연간 납입 한도는 2000만원이며 최대 5년 동안 1억원까지 납입할 수 있습니다. "
        "발생한 순이익에 대해 최대 200만원까지 비과세 혜택이 주어지며 초과 수익은 9.9% 분리과세됩니다."
    )
    
    chunks = chunker.split_text(test_text)
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 100
        # 최소 40자 이상 보정 로직 검증
        assert len(chunk) >= 40
        print(f"Chunk ({len(chunk)}): {chunk}")


def test_document_parser_txt_md():
    """DocumentParser의 일반 TXT 및 Markdown 파싱 테스트."""
    parser = DocumentParser(DEFAULT_CONFIG)
    
    # 임시 디렉토리 내에 txt, md 테스트 파일 생성
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # 1. TXT 테스트 파일
        txt_file = tmp_path / "test_doc.txt"
        txt_content = (
            "첫 번째 단락입니다. 개인종합자산관리계좌(ISA) 혜택에 관한 내용입니다.\n\n"
            "두 번째 단락입니다. 해외 주식 투자 환위험 관리 방법에 대한 상세 가이드라인입니다."
        )
        txt_file.write_text(txt_content, encoding="utf-8")
        
        passages_txt = parser.parse_file(txt_file)
        assert len(passages_txt) > 0
        assert passages_txt[0].source == "test_doc"
        assert "file_path" in passages_txt[0].metadata
        assert passages_txt[0].metadata["file_type"] == "txt"
        
        # 2. Markdown 테스트 파일
        md_file = tmp_path / "test_doc.md"
        md_content = (
            "# ISA 계좌 가이드\n\n"
            "- **비과세 한도**: 200만원 초과분 분리과세 적용\n"
            "- **의무 가입 기간**: 3년 유지 필수"
        )
        md_file.write_text(md_content, encoding="utf-8")
        
        passages_md = parser.parse_file(md_file)
        assert len(passages_md) > 0
        assert passages_md[0].metadata["file_type"] == "md"
        # HTML 태그 등 가벼운 정제 검증
        assert "<" not in passages_md[0].text
        
        
if __name__ == "__main__":
    test_financial_chunker()
    test_document_parser_txt_md()
    print("ALL TESTS PASSED")
