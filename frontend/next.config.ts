import type { NextConfig } from "next";

// 외부 노출 시 프론트(:3000) 하나만 열면 되도록 /api 요청을 백엔드로 프록시한다.
// 브라우저 → Next(:3000) → 백엔드(localhost:8000). CORS·백엔드 포트 노출 불필요.
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // SSE(/api/v1/chat/stream)를 죽이지 않으려면 반드시 꺼야 한다.
  // Next 가 프록시 응답을 gzip 으로 다시 감싸면서 text/event-stream 을 통째로 버퍼링해,
  // 브라우저에는 청크가 0개(빈 응답)로 도착한다 — 챗봇이 아무것도 못 뱉는 것처럼 보인다.
  // 백엔드(:8000) 직접 호출은 멀쩡한데 :3000 경유만 죽는 게 이 증상의 특징.
  // 정적 자산 압축은 앞단(ngrok/CDN)이 처리하므로 여기서 끄는 비용은 사실상 없다.
  compress: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_ORIGIN}/api/:path*` },
    ];
  },
};

export default nextConfig;
