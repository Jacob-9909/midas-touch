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
          background: "#04060a",
          color: "#f1f4f9",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div role="alert" style={{ textAlign: "center", padding: "2rem" }}>
          <h1 style={{ fontSize: "1.5rem", margin: 0 }}>문제가 발생했어요</h1>
          <p style={{ marginTop: "0.75rem", color: "#848e9f" }}>
            앱을 실행하는 동안 오류가 생겼습니다.
          </p>
          {error.digest && (
            <p style={{ margin: 0, color: "#848e9f", opacity: 0.7 }}>
              DIGEST · {error.digest}
            </p>
          )}
          <button
            onClick={reset}
            style={{
              marginTop: "1.5rem",
              padding: "0.5rem 1rem",
              borderRadius: "9999px",
              border: "1px solid rgba(212, 175, 96, 0.4)",
              background: "rgba(212, 175, 96, 0.2)",
              color: "#d4af37",
              cursor: "pointer",
            }}
          >
            다시 시도
          </button>
        </div>
      </body>
    </html>
  );
}
