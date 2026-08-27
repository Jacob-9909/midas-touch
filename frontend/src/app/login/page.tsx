"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ShieldChevron, Eye, EyeSlash } from "@phosphor-icons/react";

import { useSelectedUser } from "@/lib/user-context";
import { Spinner } from "@/components/ui";

export default function LoginPage() {
  const { login } = useSelectedUser();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-4">
      <div className="glass rounded-[var(--r-xl)] p-7 shadow-[var(--shadow-2)]">
        <div className="mb-6 flex items-center gap-2.5">
          <ShieldChevron
            weight="fill"
            size={22}
            className="text-gilt"
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
      </div>
    </div>
  );
}
