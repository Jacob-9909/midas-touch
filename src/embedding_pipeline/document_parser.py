"""
document_parser.py
------------------
금융 문서(PDF, TXT, MD) 통합 파서 및 청킹 엔진.

1. PDF: pypdf 기반 정제 파싱 (헤더/푸터 및 연속 공백 정제)
   - 텍스트 레이어가 손상/부재한 PDF는 자동 감지하여 Gemini 비전 전사로 폴백.
2. MD: 마크다운 구조(헤더, 목록) 분석 파싱
3. TXT: 개행 및 문장 경계 기준 텍스트 로드
4. Chunker: 한글 금융 텍스트 맞춤형 Recursive Character Splitter + Overlap 지원.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pypdf
except ImportError:
    pypdf = None

from .config import PipelineConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 데이터 모델 (기존 query_synthesizer.py의 Passage와 호환)
# ---------------------------------------------------------------------------
@dataclass
class Passage:
    """정제 및 청킹이 완료된 개별 금융 문서 단락."""

    passage_id: str
    text: str
    source: str          # 원본 파일명 또는 문서명
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 금융 텍스트 맞춤형 Chunker (Recursive Character Splitter)
# ---------------------------------------------------------------------------
class FinancialChunker:
    """
    임베딩 모델의 max_seq_length(512 토큰) 내외에 맞춤화된 지능형 Chunker.
    
    - 분할 구분자 우선순위: \n\n (단락) -> \n (줄바꿈) -> . (문장) -> " " (어절) -> "" (글자)
    - 문맥 보존을 위한 Chunk Overlap 지원.
    """

    def __init__(
        self,
        chunk_size: int = 700,      # 한글 기준 약 400~500 토큰
        chunk_overlap: int = 150,   # 문맥 보존 오버랩
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        """Recursive Character Splitting 수행 (Markdown 헤더 및 금융 단락 고려)."""
        if not text:
            return []

        # Markdown의 대/중/소 헤더(#, ##, ###)를 최우선 구분자로 지정하여 의미적 정보 절단 차단
        separators = ["\n# ", "\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]
        return self._split_recursive(text, separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """재귀적으로 구분자를 활용해 분할한 후 적절한 오버랩을 주어 그룹화."""
        if len(text) <= self.chunk_size:
            return [text]

        # 사용할 수 있는 구분자 탐색
        separator = ""
        next_separators: list[str] = []
        for i, sep in enumerate(separators):
            if sep == "":
                separator = sep
                next_separators = separators[i + 1 :]
                break
            if sep in text:
                separator = sep
                next_separators = separators[i + 1 :]
                break

        # 구분자 기준으로 1차 분할
        if separator != "":
            splits = text.split(separator)
        else:
            splits = list(text)

        # 빈 조각 제거 및 구분자 복원
        final_splits: list[str] = []
        for s in splits:
            s = s.strip()
            if not s:
                continue
            final_splits.append(s)

        # 각 조각들이 여전히 크면 다음 우선순위 구분자로 재귀 분할
        refined_splits: list[str] = []
        for split in final_splits:
            if len(split) > self.chunk_size:
                refined_splits.extend(self._split_recursive(split, next_separators))
            else:
                refined_splits.append(split)

        # 조각들을 Chunk Size와 Overlap 규칙에 부합하게 결합
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for split in refined_splits:
            split_len = len(split)
            # 현재 청크에 추가했을 때 넘치는지 확인
            if current_length + split_len + (len(separator) if current_chunk else 0) > self.chunk_size:
                if current_chunk:
                    # 완성된 청크 저장
                    chunks.append(separator.join(current_chunk))
                    
                    # 오버랩 보존을 위한 롤백 슬라이딩
                    # 뒤에서부터 오버랩 사이즈 이하가 될 때까지 복구
                    overlap_chunk: list[str] = []
                    overlap_len = 0
                    for prev_split in reversed(current_chunk):
                        prev_len = len(prev_split)
                        if overlap_len + prev_len + (len(separator) if overlap_chunk else 0) <= self.chunk_overlap:
                            overlap_chunk.insert(0, prev_split)
                            overlap_len += prev_len + len(separator)
                        else:
                            break
                    current_chunk = overlap_chunk
                    current_length = overlap_len
                
            current_chunk.append(split)
            current_length += split_len + (len(separator) if len(current_chunk) > 1 else 0)

        if current_chunk:
            chunks.append(separator.join(current_chunk))

        # 너무 짧은 청크(예: 30자 미만) 병합 또는 보정
        valid_chunks = [c.strip() for c in chunks if len(c.strip()) >= 40]
        return valid_chunks


# ---------------------------------------------------------------------------
# 통합 문서 파서
# ---------------------------------------------------------------------------
class DocumentParser:
    """
    다양한 형식(PDF, TXT, MD)의 금융 문서를 자동으로 파싱하고
    고품질 임베딩 단락(Passage)으로 정제 청킹하는 리더.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config
        self._chunker = FinancialChunker(
            chunk_size=750,  # 한국어 금융 문맥 보존용 최적 크기
            chunk_overlap=150,
        )

    def parse_file(self, path: Path) -> list[Passage]:
        """
        단일 파일 경로를 읽어 확장자에 알맞게 파싱 및 청킹 수행.

        Returns:
            Passage 인스턴스 목록
        """
        if not path.exists():
            logger.error("파일이 존재하지 않습니다: %s", path)
            return []

        suffix = path.suffix.lower()
        # Mac 환경에서의 한글 자모 분리 방지를 위해 NFC 정규화 적용
        source_name = unicodedata.normalize('NFC', path.stem)

        logger.info("문서 파싱 중: %s (형식: %s)", path.name, suffix)

        try:
            if suffix == ".pdf":
                raw_text = self._parse_pdf(path)
            elif suffix == ".md":
                raw_text = self._parse_markdown(path)
            elif suffix in (".txt", ".jsonl"):
                raw_text = self._parse_text(path)
            else:
                logger.warning("지원하지 않는 파일 형식입니다. 건너뜁니다: %s", path.name)
                return []

            # 한글 인코딩 및 임베딩 퀄리티를 위해 본문도 NFC 정규화 적용
            raw_text = unicodedata.normalize('NFC', raw_text)

            # 텍스트 청킹 실행
            chunks = self._chunker.split_text(raw_text)
            
            passages = [
                Passage(
                    passage_id=f"{source_name}_{idx:05d}",
                    text=chunk,
                    source=source_name,
                    metadata={"file_path": str(path), "chunk_index": idx, "file_type": suffix[1:]},
                )
                for idx, chunk in enumerate(chunks)
            ]

            logger.info("-> %s 파싱 완료: %d개 단락 생성", path.name, len(passages))
            return passages

        except Exception as exc:
            logger.exception("%s 파싱 실패: %s", path.name, exc)
            return []

    # ------------------------------------------------------------------
    # 포맷별 파싱 헬퍼
    # ------------------------------------------------------------------
    def _parse_pdf(self, path: Path) -> str:
        """pypdf 기반 PDF 텍스트 추출 및 여백 노이즈 정제."""
        if pypdf is None:
            raise ImportError(
                "PDF 파싱을 위해서는 pypdf 라이브러리가 필요합니다. "
                "먼저 'uv sync' 또는 'pip install pypdf'를 실행하세요."
            )

        reader = pypdf.PdfReader(path)
        pages_text: list[str] = []

        # 여백 머리글, 바닥글, 페이지 번호 제거용 정규식 패턴들
        pg_num_pattern = re.compile(r"^\s*-\s*\d+\s*-\s*$|^\s*\d+\s*$/?\s*\d*\s*$", re.MULTILINE)

        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue

            # 한글 인코딩 자모 분리 교정
            text = unicodedata.normalize('NFC', text)

            cleaned_lines: list[str] = []
            for line in text.splitlines():
                line = line.strip()
                # 페이지 번호 패턴 제거
                if pg_num_pattern.match(line):
                    continue
                # 머리글/바닥글 노이즈 필터링 (보통 회사명이나 보고서명이 끝자리에 반복됨)
                if len(line) < 4 and line.isdigit():
                    continue
                cleaned_lines.append(line)

            page_refined = "\n".join(cleaned_lines)
            
            # 연속된 개행, 연속된 스페이스 정제
            page_refined = re.sub(r" {2,}", " ", page_refined)
            page_refined = re.sub(r"\n{3,}", "\n\n", page_refined)
            pages_text.append(page_refined)

        final_pdf_text = "\n\n".join(pages_text)

        # 텍스트 레이어 품질 검증: 너무 짧거나(스캔본) 글자 깨짐(폰트 매핑 손상)이면 비전 전사로 폴백.
        stripped = final_pdf_text.strip()
        too_short = len(stripped) < 50
        corrupted = self._looks_corrupted(stripped)
        if too_short or corrupted:
            reason = "텍스트가 거의 추출되지 않음(스캔본 추정)" if too_short else "텍스트 레이어 손상(글자 단위 깨짐) 감지"
            logger.warning(
                "[PDF 텍스트 추출 경고] '%s': %s. Gemini 비전 전사로 폴백합니다.",
                path.name, reason,
            )
            vision_text = self._parse_pdf_vision(path)
            if vision_text.strip():
                return vision_text
            logger.error(
                "[PDF] '%s' 비전 전사도 실패했습니다. pypdf 추출 결과를 그대로 반환합니다.", path.name
            )

        return final_pdf_text

    @staticmethod
    def _looks_corrupted(text: str, sample_chars: int = 4000) -> bool:
        """텍스트 레이어 손상 감지: 공백으로 분리된 토큰 대부분이 1글자면 깨진 것으로 판단.

        정상 한글 본문은 '주택임대소득' 같은 다글자 어절이 대부분이지만,
        폰트 매핑이 손상된 PDF는 '주 택 임 대 소 득'처럼 글자마다 공백이 끼어
        1글자 토큰 비율이 비정상적으로 높아진다.
        """
        sample = text[:sample_chars]
        tokens = [t for t in sample.split() if t]
        if len(tokens) < 20:
            return False
        single = sum(1 for t in tokens if len(t) == 1)
        return (single / len(tokens)) > 0.45

    def _parse_pdf_vision(self, path: Path) -> str:
        """손상/스캔 PDF를 페이지 이미지로 렌더링한 뒤 Gemini 비전으로 전사하여 markdown 텍스트로 복원."""
        try:
            import pymupdf
            from google import genai
            from google.genai import types
        except ImportError as exc:
            logger.error(
                "비전 전사를 위해 pymupdf, google-genai 가 필요합니다 (uv add pymupdf google-genai): %s", exc
            )
            return ""

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY 가 설정되지 않아 비전 전사를 진행할 수 없습니다.")
            return ""

        model = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")
        dpi = int(os.environ.get("PDF_VISION_DPI", "150"))
        max_workers = int(os.environ.get("PDF_VISION_WORKERS", "8"))
        prompt = (
            "이 이미지는 한국 주택/금융 세금 안내 책자의 한 페이지다. "
            "페이지에 보이는 본문 텍스트를 한국어 마크다운으로 정확히 그대로 전사(transcribe)하라. "
            "표는 마크다운 표로 변환하라. 머리글/꼬리글/페이지번호/URL/워터마크는 제외하고 본문만 출력하라. "
            "추가 설명이나 코드펜스 없이 전사 결과 텍스트만 출력하라."
        )

        doc = pymupdf.open(path)
        client = genai.Client(api_key=api_key)
        n = doc.page_count
        logger.info("[PDF 비전] '%s' %d페이지 전사 시작 (model=%s, dpi=%d, workers=%d)...",
                    path.name, n, model, dpi, max_workers)

        # 페이지 이미지를 미리 렌더링(메인 스레드에서 pymupdf 접근, 동시성은 API 호출에만 적용)
        page_images = [doc[i].get_pixmap(dpi=dpi).tobytes("png") for i in range(n)]

        def transcribe(idx_img: tuple[int, bytes]) -> tuple[int, str]:
            idx, img = idx_img
            for attempt in range(1, 4):
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=[types.Part.from_bytes(data=img, mime_type="image/png"), prompt],
                    )
                    text = (resp.text or "").strip()
                    # 혹시 모델이 코드펜스를 붙이면 제거
                    text = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", text).strip()
                    return idx, text
                except Exception as exc:  # 일시적 오류 재시도
                    logger.warning("[PDF 비전] %d/%d 페이지 전사 실패(시도 %d/3): %s", idx + 1, n, attempt, exc)
            logger.error("[PDF 비전] %d/%d 페이지 전사 최종 실패, 빈 텍스트로 처리.", idx + 1, n)
            return idx, ""

        results: list[str] = [""] * n
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for idx, text in pool.map(transcribe, enumerate(page_images)):
                results[idx] = text
                if (idx + 1) % 20 == 0:
                    logger.info("[PDF 비전] 진행: %d/%d 페이지 전사 완료", idx + 1, n)

        ok = sum(1 for r in results if r)
        logger.info("[PDF 비전] '%s' 전사 완료: %d/%d 페이지 성공", path.name, ok, n)
        return "\n\n".join(r for r in results if r)

    def _parse_markdown(self, path: Path) -> str:
        """마크다운 파일 읽기 및 가벼운 문법 노이즈(코드블럭 기호 등) 정제."""
        text = path.read_text(encoding="utf-8")
        
        # 이미지 링크, 마크다운 링크 등 가벼운 정제 가능 ( RAG 검색 임베딩 퀄리티에 유리 )
        # 예: ![image](path) -> ""
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        # HTML 태그 제거
        text = re.sub(r"<[^>]*>", "", text)
        
        # 줄바꿈 및 간격 정규화
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _parse_text(self, path: Path) -> str:
        """일반 텍스트 파일 로드 및 공백 정규화."""
        text = path.read_text(encoding="utf-8")
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
