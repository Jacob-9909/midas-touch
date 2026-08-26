"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ShieldChevron } from "@phosphor-icons/react";

import { useSelectedUser } from "@/lib/user-context";

export default function LoginPage() {
  const { login } = useSelectedUser();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center">
      <div className="glass p-7 shadow-[var(--shadow-2)]">
        <div className="mb-6 flex items-center gap-2.5">
          <ShieldChevron
            weight="fill"
            size={22}
            className="text-gilt"
          />
          <h1 className="font-display text-xl font-semibold tracking-tight">Midas Touch 로그인</h1>
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
              className="w-full rounded-[var(--r-sm)] border border-line bg-[var(--ink-2)] px-3 py-2 text-sm text-fg outline-none transition focus:border-accent focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)]"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-mono-spec text-muted">비밀번호</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-[var(--r-sm)] border border-line bg-[var(--ink-2)] px-3 py-2 text-sm text-fg outline-none transition focus:border-accent focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)]"
            />
          </label>

          {error && (
            <p className="rounded-[var(--r-sm)] border border-negative/40 bg-negative/10 px-3 py-2 text-xs text-negative">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="btn-accent w-full"
          >
            {busy ? "로그인 중…" : "로그인"}
          </button>
        </form>
      </div>
    </div>
  );
}
