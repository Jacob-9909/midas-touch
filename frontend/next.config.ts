import type { NextConfig } from "next";

// 외부 노출 시 프론트(:3000) 하나만 열면 되도록 /api 요청을 백엔드로 프록시한다.
// 브라우저 → Next(:3000) → 백엔드(localhost:8000). CORS·백엔드 포트 노출 불필요.
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Next의 gzip이 프록시된 SSE(/api/v1/chat/stream)를 압축하면서 스트림을 버퍼링해
  // 답변이 토큰 단위로 안 흐르고 끝에 통째로 나왔다("확 나와"). 압축을 꺼 스트리밍을 살린다.
  // (정적 자산 압축은 운영 시 앞단 프록시/CDN이 담당하면 된다.)
  compress: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_ORIGIN}/api/:path*` },
    ];
  },
};

export default nextConfig;
