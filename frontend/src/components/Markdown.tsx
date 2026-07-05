"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import type { Components } from "react-markdown";

// 채팅/리포트용 마크다운 렌더러.
// - remark-gfm: 표·취소선·자동링크 등 GFM 지원
// - remark-breaks: 단일 개행(\n)을 <br>로 — 마크다운이 아닌 평문도 원문 줄바꿈 그대로 보이게 함
// 스타일은 components 맵으로 주입해 @tailwindcss/typography 의존 없이 자기완결.
const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
  h1: ({ children }) => <h1 className="mb-2 mt-3 text-base font-semibold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-3 text-sm font-semibold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1.5 mt-2.5 text-sm font-semibold first:mt-0">{children}</h3>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-line pl-3 text-muted">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-line" />,
  // 표는 좁은 버블에서 넘칠 수 있어 가로 스크롤 컨테이너로 감싼다.
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-line bg-[color-mix(in_srgb,var(--fg)_5%,transparent)] px-2 py-1 text-left font-medium">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="border border-line px-2 py-1">{children}</td>,
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg bg-[color-mix(in_srgb,var(--fg)_6%,transparent)] p-3 text-xs">
      {children}
    </pre>
  ),
  code: ({ className, children }) => {
    const isBlock = /\n/.test(String(children)) || (className ?? "").startsWith("language-");
    return isBlock ? (
      <code className={`font-mono ${className ?? ""}`}>{children}</code>
    ) : (
      <code className="rounded bg-[color-mix(in_srgb,var(--fg)_8%,transparent)] px-1 py-0.5 font-mono text-[0.85em]">
        {children}
      </code>
    );
  },
};

export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={components}>
      {children}
    </ReactMarkdown>
  );
}
