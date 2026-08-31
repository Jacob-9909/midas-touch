"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ShieldChevron, Eye, EyeSlash } from "@phosphor-icons/react";

import { useSelectedUser } from "@/lib/user-context";
import { Spinner } from "@/components/ui";

/** 공개 체험 계정. 회원가입 경로가 없는 상태라 이게 없으면 배포 URL로 들어온
 *  심사위원·외부 방문자는 첫 화면에서 그대로 막힌다. 노출을 전제로 만든 계정이므로
 *  번들에 박혀 있는 것이 문제가 아니다. 자격은 set_user_password.py 로 발급한다. */
const DEMO_EMAIL = "demo@midas.touch";
const DEMO_PASSWORD = "MidasDemo2026!";

export default function LoginPage() {
  const { login } = useSelectedUser();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signIn(id: string, pw: string) {
    setBusy(true);
    setError(null);
    try {
      await login(id.trim(), pw);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await signIn(email, password);
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-4">
      <div className="glass rounded-[var(--r-xl)] p-7 shadow-[var(--shadow-2)]">
        <div className="mb-6 flex items-center gap-2.5">
          <ShieldChevron
            weight="fill"
            size={22}
            className="text-accent"
          />
          <h1 className="font-display text-xl font-semibold tracking-tight text-fg">Midas Touch 로그인</h1>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-mono-spec text-muted">이메일</span>
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="field w-full px-3 py-2 text-sm"
              placeholder="user@example.com"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-mono-spec text-muted">비밀번호</span>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field w-full px-3 py-2 pr-10 text-sm"
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 표시"}
                className="btn-ghost btn-icon absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 text-muted hover:text-fg"
              >
                {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>

          {error && (
            <p className="rounded-[var(--r-sm)] border border-negative/40 bg-negative/10 px-3 py-2 text-xs text-negative">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="btn-accent w-full flex items-center justify-center gap-2 mt-2"
          >
            {busy ? (
              <>
                <Spinner className="h-4 w-4 text-white" />
                <span>로그인 중…</span>
              </>
            ) : (
              "로그인"
            )}
          </button>
        </form>

        {/* 체험 계정 안내 — 회원가입이 없으므로 여기서 막히면 서비스를 볼 방법이 없다. */}
        <div className="mt-6 rounded-[var(--r-md)] border border-accent/30 bg-accent/8 p-4">
          <p className="text-xs font-semibold text-fg">계정 없이 둘러보기</p>
          <p className="mt-1.5 text-xs leading-relaxed text-muted">
            체험용 공개 계정을 준비해 두었습니다. 아래 버튼을 누르면 바로 들어갑니다.
            <br />
            <span className="font-mono-spec text-fg">{DEMO_EMAIL}</span> ·{" "}
            <span className="font-mono-spec text-fg">{DEMO_PASSWORD}</span>
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={() => signIn(DEMO_EMAIL, DEMO_PASSWORD)}
            className="btn-ghost mt-3 w-full border-accent/40 text-sm text-accent hover:bg-accent/15"
          >
            체험 계정으로 바로 시작
          </button>
        </div>
      </div>
    </div>
  );
}
