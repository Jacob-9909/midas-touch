import type { NextConfig } from "next";

// 외부 노출 시 프론트(:3000) 하나만 열면 되도록 /api 요청을 백엔드로 프록시한다.
// 브라우저 → Next(:3000) → 백엔드(localhost:8000). CORS·백엔드 포트 노출 불필요.
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_ORIGIN}/api/:path*` },
    ];
  },
};

export default nextConfig;
