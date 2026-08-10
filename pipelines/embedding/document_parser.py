"""
document_parser.py
------------------
금융 문서(PDF, TXT, MD) 통합 파서 및 청킹 엔진.

1. PDF: pypdf 기반 정제 파싱 (헤더/푸터 및 연속 공백 정제)
   - 텍스트 레이어가 손상/부재한 PDF는 자동 감지하여 경고 로그를 남긴다(비전 전사 없음).
2. MD: 마크다운 구조(헤더, 목록) 분석 파싱
3. TXT: 개행 및 문장 경계 기준 텍스트 로드
4. Chunker: 한글 금융 텍스트 맞춤형 Recursive Character Splitter + Overlap 지원.
"""

from __future__ import annotations

import logging
import re
import unicodedata
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
    - [고도화] AutoTokenizer를 활용한 실제 토큰 수 기반 정밀 분할. 
              (실패 시 글자 수 기반 청킹으로 자동 Fallback)
    """

    def __init__(
        self,
        model_name: str = "nlpai-lab/KURE-v1",
        chunk_size: int = 450,      # 토큰 기준 상한
        chunk_overlap: int = 100,   # 토큰 기준 오버랩
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model_name = model_name
        self.tokenizer = None
        self.use_token_mode = False

        try:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.use_token_mode = True
            logger.info("AutoTokenizer('%s')를 활용한 토큰 기반 청킹이 활성화되었습니다. (chunk_size=%d, overlap=%d)", model_name, chunk_size, chunk_overlap)
        except Exception as exc:
            logger.warning(
                "토크나이저 로드 실패 (%s). 글자 수 기반 청킹(Fallback)으로 전환합니다.", exc
            )
            # 글자 수 기반 fallback 세팅
            self.chunk_size = 700      # 한글 기준 약 400~500 토큰에 대응
            self.chunk_overlap = 150
            self.use_token_mode = False

    def _get_length(self, text: str) -> int:
        """현재 모드에 맞춰 텍스트의 길이를 반환 (토큰 수 또는 글자 수)."""
        if self.use_token_mode and self.tokenizer is not None:
            try:
                return len(self.tokenizer.encode(text, add_special_tokens=False))
            except Exception:
                pass
        return len(text)

    def split_text(self, text: str) -> list[str]:
        """Recursive Character Splitting 수행 (Markdown 헤더 및 금융 단락 고려)."""
        if not text:
            return []

        # Markdown의 대/중/소 헤더(#, ##, ###)를 최우선 구분자로 지정하여 의미적 정보 절단 차단
        separators = ["\n# ", "\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]
        return self._split_recursive(text, separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """재귀적으로 구분자를 활용해 분할한 후 적절한 오버랩을 주어 그룹화."""
        if self._get_length(text) <= self.chunk_size:
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
            if self._get_length(split) > self.chunk_size:
                refined_splits.extend(self._split_recursive(split, next_separators))
            else:
                refined_splits.append(split)

        # 조각들을 Chunk Size와 Overlap 규칙에 부합하게 결합
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for split in refined_splits:
            split_len = self._get_length(split)
            sep_len = self._get_length(separator) if current_chunk else 0
            # 현재 청크에 추가했을 때 넘치는지 확인
            if current_length + split_len + sep_len > self.chunk_size and current_chunk:
                # 완성된 청크 저장
                chunks.append(separator.join(current_chunk))
                
                # 오버랩 보존을 위한 롤백 슬라이딩
                # 뒤에서부터 오버랩 사이즈 이하가 될 때까지 복구
                overlap_chunk: list[str] = []
                overlap_len = 0
                for prev_split in reversed(current_chunk):
                    prev_len = self._get_length(prev_split)
                    sep_overlap_len = self._get_length(separator) if overlap_chunk else 0
                    if overlap_len + prev_len + sep_overlap_len <= self.chunk_overlap:
                        overlap_chunk.insert(0, prev_split)
                        overlap_len += prev_len + sep_overlap_len
                    else:
                        break
                current_chunk = overlap_chunk
                current_length = overlap_len
                
            current_chunk.append(split)
            sep_len = self._get_length(separator) if len(current_chunk) > 1 else 0
            current_length += split_len + sep_len

        if current_chunk:
            chunks.append(separator.join(current_chunk))

        # 너무 짧은 청크(예: 토큰 모드에서는 25토큰 미만, 글자 모드에서는 40자 미만) 병합 또는 보정
        min_limit = 25 if self.use_token_mode else 40
        valid_chunks = [c.strip() for c in chunks if self._get_length(c.strip()) >= min_limit]
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
        """pymupdf를 기본으로 사용하고 pypdf를 보완적으로 사용하여 텍스트 및 표 데이터를 고품질로 추출."""
        raw_text = ""
        
        # 1. pymupdf(fitz)를 이용한 고품질 파싱 시도 (표 추출 포함)
        try:
            import pymupdf
            doc = pymupdf.open(path)
            pages_text: list[str] = []
            
            for page_idx, page in enumerate(doc):
                page_text = page.get_text("text") or ""
                
                # 표(Table) 추출하여 마크다운 표로 변환 및 삽입
                tables_md = []
                try:
                    tables = page.find_tables()
                    for table in tables:
                        # table.extract()는 이중 리스트 [ [cell1, cell2], [cell3, cell4] ] 형태 반환
                        grid = table.extract()
                        if grid and len(grid) > 0:
                            # 마크다운 표로 변환
                            headers = [str(h or "").strip() for h in grid[0]]
                            col_count = len(headers)
                            md_lines = []
                            md_lines.append("| " + " | ".join(headers) + " |")
                            md_lines.append("| " + " | ".join(["---"] * col_count) + " |")
                            for row in grid[1:]:
                                cells = [str(c or "").strip().replace('\n', ' ') for c in row]
                                # 혹시 row의 열 개수가 header와 다를 경우 맞추어 줌
                                if len(cells) < col_count:
                                    cells += [""] * (col_count - len(cells))
                                else:
                                    cells = cells[:col_count]
                                md_lines.append("| " + " | ".join(cells) + " |")
                            table_md_str = "\n".join(md_lines)
                            tables_md.append(table_md_str)
                except Exception as t_exc:
                    logger.debug("페이지 %d 표 추출 실패: %s", page_idx + 1, t_exc)
                
                # 정제 작업 수행
                page_refined = unicodedata.normalize('NFC', page_text)
                
                # 페이지 번호 패턴 제거
                pg_num_pattern = re.compile(r"^\s*-\s*\d+\s*-\s*$|^\s*\d+\s*$/?\s*\d*\s*$", re.MULTILINE)
                lines = [line.strip() for line in page_refined.splitlines() if line.strip() and not pg_num_pattern.match(line.strip())]
                page_refined = "\n".join(lines)
                
                # 표가 발견되었으면 본문에 부착
                if tables_md:
                    page_refined += "\n\n[추출된 표 데이터]\n" + "\n\n".join(tables_md)
                
                pages_text.append(page_refined)
            
            raw_text = "\n\n".join(pages_text)
            logger.info("pymupdf로 PDF '%s' 파싱 성공 (페이지 수: %d)", path.name, len(doc))
        except Exception as exc:
            logger.warning("pymupdf 파싱 실패, pypdf로 보완 처리합니다: %s", exc)
            raw_text = ""

        # 2. pymupdf 결과가 비어있거나 실패했을 경우 pypdf로 폴백
        if not raw_text.strip():
            if pypdf is None:
                raise ImportError(
                    "PDF 파싱을 위해서는 pypdf 라이브러리가 필요합니다. "
                    "먼저 'uv sync' 또는 'pip install pypdf'를 실행하세요."
                )
            reader = pypdf.PdfReader(path)
            pages_text = []
            pg_num_pattern = re.compile(r"^\s*-\s*\d+\s*-\s*$|^\s*\d+\s*$/?\s*\d*\s*$", re.MULTILINE)
            
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if not text:
                    continue
                text = unicodedata.normalize('NFC', text)
                cleaned_lines: list[str] = []
                for line in text.splitlines():
                    line = line.strip()
                    if pg_num_pattern.match(line):
                        continue
                    if len(line) < 4 and line.isdigit():
                        continue
                    cleaned_lines.append(line)
                page_refined = "\n".join(cleaned_lines)
                page_refined = re.sub(r" {2,}", " ", page_refined)
                page_refined = re.sub(r"\n{3,}", "\n\n", page_refined)
                pages_text.append(page_refined)
            raw_text = "\n\n".join(pages_text)
            logger.info("pypdf로 PDF '%s' 보완 파싱 완료", path.name)

        # 3. 공백 및 개행 최종 정밀 정제
        raw_text = re.sub(r" {2,}", " ", raw_text)
        raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)

        # 4. 텍스트 깨짐 및 스캔본 감지 시 경고만 남긴다(추출 결과는 그대로 반환).
        stripped = raw_text.strip()
        too_short = len(stripped) < 50
        corrupted = self._looks_corrupted(stripped)

        if too_short or corrupted:
            reason = "텍스트가 거의 추출되지 않음(스캔본 추정)" if too_short else "텍스트 레이어 손상(글자 단위 깨짐) 감지"
            logger.warning(
                "[PDF 텍스트 추출 경고] '%s': %s. 해당 문서는 품질이 낮은 상태로 적재됩니다.",
                path.name, reason,
            )

        return raw_text

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
