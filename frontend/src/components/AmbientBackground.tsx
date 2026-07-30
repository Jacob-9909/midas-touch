"use client";

// 전역 앰비언트 광원. 앱 전체에서 유일한 WebGL 캔버스다.
//
// 켜지는 조건:
//   - 다크 테마일 때만. 라이트에선 골드 오로라가 흰 배경에 탁하게 뜬다.
//   - prefers-reduced-motion 미설정.
//   - 마운트 이후(SSR 시 WebGL 없음).
//   - 해당 라우트가 자체 WebGL 배경을 갖고 있지 않을 것.
// 꺼져 있어도 globals.css의 그레인·글로우는 그대로 남아 화면이 비지 않는다.

import { useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";
import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";
import { useTheme } from "@/lib/theme";

// WebGL은 서버에서 못 돈다 → 클라이언트에서만 로드하고 번들도 분리한다.
const SoftAurora = dynamic(() => import("@/components/bits/SoftAurora"), { ssr: false });

/**
 * 자체 WebGL 배경을 소유한 라우트. 여기서는 전역 앰비언트를 양보한다.
 * 캔버스 총량을 1개로 묶는 장치이자, 골드 광원이 두 겹으로 겹쳐 과포화되는 걸 막는다.
 * 페이지에 WebGL 배경을 새로 넣는다면 반드시 여기에 경로를 추가할 것.
 */
const WEBGL_OWNED_ROUTES = ["/graph"];

export default function AmbientBackground() {
  const { theme } = useTheme();
  const reduce = useReducedMotion();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  // 마운트 1회 플래그. 서버엔 matchMedia도 테마 동기화도 없어 하이드레이션이 어긋난다.
  // theme.tsx의 동기화와 같은 이유로 effect가 정답이라 규칙을 끈다.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  const routeOwnsWebGL = WEBGL_OWNED_ROUTES.some(
    (r) => pathname === r || pathname.startsWith(`${r}/`),
  );

  if (!mounted || reduce || theme !== "dark" || routeOwnsWebGL) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-[70vh] opacity-45 [mask-image:linear-gradient(to_bottom,black_0%,black_25%,transparent_95%)]"
    >
      <SoftAurora
        speed={0.35}
        scale={1.7}
        // bandHeight는 밴드의 세로 위치(1.0 = 컨테이너 최상단).
        // 낮으면 광원 리본이 히어로 문구를 가로질러 읽기를 방해한다.
        bandHeight={0.98}
        // bandSpread는 지수라 값이 클수록 피크가 날카로워진다. 낮춰서 넓고 흐리게.
        bandSpread={0.7}
        brightness={0.62}
        noiseAmplitude={0.62}
        octaveDecay={0.3}
        colorSpeed={0.5}
        // 배경은 pointer-events-none이라 마우스 이벤트가 닿지 않는다. 리스너만 낭비.
        enableMouseInteraction={false}
      />
    </div>
  );
}
