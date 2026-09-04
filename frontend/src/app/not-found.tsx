import Link from "next/link";

// 요청한 경로가 없을 때의 404 폴백.
export default function NotFound() {
  return (
    <div className="mx-auto my-24 max-w-md px-4 text-center">
      <p className="eyebrow">404 · NOT FOUND</p>
      <h1 className="mt-3 font-display text-4xl tracking-tight text-fg sm:text-5xl">
        페이지를 찾을 수 없어요
      </h1>
      <p className="mx-auto mt-4 max-w-[48ch] text-xs leading-relaxed text-muted">
        주소가 바뀌었거나 삭제된 페이지일 수 있습니다.
        홈에서 다시 원하는 화면으로 이동해 주세요.
      </p>
      <div className="mt-8 flex justify-center">
        <Link
          href="/"
          className="btn-accent"
        >
          홈으로 돌아가기 →
        </Link>
      </div>
    </div>
  );
}
