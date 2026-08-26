// 챗 assistant 답변 말미의 "출처" 섹션 감지/분리 헬퍼.
// 백엔드 synthesize 노드(nodes/synthesize.py)가 LLM 호출과 무관하게 코드로 덧붙이는 형식:
//   "\n\n---\n출처:\n[1] <source> (<passage_id>)\n[2] ..."
// LLM 본문의 우연한 일치를 걸러내기 위해 구분선 바로 다음 '출처:' 헤더와
// [1]부터 시작해 1씩 늘어나는 연속 항목으로만 이루어진 꼬리를 출처 섹션으로 인정한다.

const SOURCES_HEADER = "\n---\n출처:";
const SOURCE_ITEM_RE = /^\[(\d+)\] (.+) \((.+)\)$/;

export interface ChatSource {
  index: number;
  source: string;
  passageId: string;
}

export function splitChatSources(
  content: string,
): { body: string; sources: ChatSource[] } {
  const headerAt = content.lastIndexOf(SOURCES_HEADER);
  if (headerAt === -1) return { body: content, sources: [] };

  const lines = content.slice(headerAt + SOURCES_HEADER.length).split("\n");
  const sources: ChatSource[] = [];
  for (let i = 0; i < lines.length; i++) {
    const m = SOURCE_ITEM_RE.exec(lines[i]);
    if (!m || Number(m[1]) !== i + 1) {
      // 항목이 아니거나 번호가 연속하지 않으면 우리 형식이 아니다 — 원문 그대로 렌더.
      return { body: content, sources: [] };
    }
    sources.push({ index: Number(m[1]), source: m[2], passageId: m[3] });
  }
  return { body: content.slice(0, headerAt), sources };
}
