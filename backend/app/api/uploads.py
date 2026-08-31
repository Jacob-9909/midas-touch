"""업로드 크기 상한 헬퍼 — 첨부 파일 DoS(메모리·디스크 소진) 방어.

공개 URL(심사 기간 AUTH_ENABLED=false)에서 첨부 엔드포인트가 무인증으로 열리므로,
바이트를 전부 읽고 나서 재는 방식은 이미 메모리를 다 먹은 뒤라 방어가 되지 않는다.
청크로 읽으며 상한을 넘는 즉시 중단해 상한 밖 바이트는 메모리에 올리지 않는다.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

# 약 100페이지 PDF 상당(텍스트+이미지 혼합 여유분 포함). 순수 텍스트 세법 PDF는 이보다 훨씬 작다.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_CHUNK = 1 << 20  # 1MB


async def read_upload_capped(file: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """UploadFile을 청크로 읽되 max_bytes를 넘으면 413으로 거부한다.

    상한 초과 시 남은 바이트를 계속 읽지 않으므로, 거대한 업로드가 서버 메모리를
    무제한으로 점유하는 것을 막는다.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"파일이 너무 큽니다(최대 {max_bytes // (1024 * 1024)}MB, 약 100페이지 PDF).",
            )
        chunks.append(chunk)
    return b"".join(chunks)
