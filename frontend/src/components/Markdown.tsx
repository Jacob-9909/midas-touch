"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { Copy, Check } from "@phosphor-icons/react";
import type { Components } from "react-markdown";

function CodeBlock({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const text = String(children).replace(/\n$/, "");
  const lang = className?.replace("language-", "") || "code";

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div className="relative my-3 rounded-xl border border-line bg-[var(--ink-2)] overflow-hidden font-mono-spec">
      <div className="flex items-center justify-between border-b border-line/60 bg-surface/40 px-3 py-1.5 text-[11px] text-muted">
        <span className="uppercase font-semibold tracking-wider text-accent">{lang}</span>
        <button
          type="button"
          onClick={onCopy}
          aria-label="코드 복사"
          className="flex items-center gap-1 hover:text-fg transition-colors px-1.5 py-0.5 rounded text-[10px]"
        >
          {copied ? (
            <>
              <Check size={12} weight="bold" className="text-positive" />
              <span className="text-positive font-medium">복사됨</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>복사</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-xs text-fg/90 leading-relaxed font-mono-spec">
        <code>{text}</code>
      </pre>
    </div>
  );
}

// 채팅/리포트용 마크다운 렌더러.
const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed break-keep">{children}</p>,
  h1: ({ children }) => <h1 className="mb-2 mt-3 text-base font-semibold first:mt-0 break-keep">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-3 text-sm font-semibold first:mt-0 break-keep">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1.5 mt-2.5 text-sm font-semibold first:mt-0 break-keep">{children}</h3>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed break-keep">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-fg">{children}</strong>,
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
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => {
    const isBlock = /\n/.test(String(children)) || (className ?? "").startsWith("language-");
    return isBlock ? (
      <CodeBlock className={className}>{children}</CodeBlock>
    ) : (
      <code className="rounded bg-[color-mix(in_srgb,var(--fg)_8%,transparent)] px-1.5 py-0.5 font-mono-spec text-[0.85em] text-accent">
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
