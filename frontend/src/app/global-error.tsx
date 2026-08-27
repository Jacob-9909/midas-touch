"use client";

// 루트 레이아웃 자체에서 던져진 에러 처리. 레이아웃을 대체하므로 html/body를 직접 그린다.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="ko">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a10",
          color: "#eceef4",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        <div role="alert" style={{ textAlign: "center", padding: "2rem", maxWidth: "420px" }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>문제가 발생했어요</h1>
          <p style={{ marginTop: "0.75rem", color: "#9094a8", fontSize: "0.875rem", lineHeight: 1.6 }}>
            앱을 실행하는 동안 치명적인 오류가 생겼습니다.
          </p>
          {error.digest && (
            <p style={{ margin: "0.5rem 0 0 0", color: "#6d7186", fontSize: "0.75rem", fontFamily: "monospace" }}>
              DIGEST · {error.digest}
            </p>
          )}
          <button
            onClick={reset}
            style={{
              marginTop: "1.5rem",
              padding: "0.6rem 1.5rem",
              borderRadius: "9999px",
              border: "none",
              background: "linear-gradient(135deg, #6c5cff 0%, #8b7dff 100%)",
              color: "#ffffff",
              fontSize: "0.875rem",
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: "0 4px 14px 0 rgba(108, 92, 255, 0.39)",
            }}
          >
            다시 시도
          </button>
        </div>
      </body>
    </html>
  );
}
