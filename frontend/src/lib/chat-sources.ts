// 챗 assistant 답변 말미의 "방어 증명" 및 "출처" 섹션 감지/분리 헬퍼.
// 백엔드 synthesize 노드(nodes/synthesize.py)가 생성하는 형식:
//   <본문>
//   \n---\n🛡 방어 증명:\n- 검색 도구...
//   \n---\n출처:\n[1] <source> (<passage_id>)...

const DEFENSE_HEADER = "\n---\n🛡 방어 증명:";
const SOURCES_HEADER = "\n---\n출처:";
const SOURCE_ITEM_RE = /^\[(\d+)\] (.+) \((.+)\)$/;

export interface ChatSource {
  index: number;
  source: string;
  passageId: string;
}

export interface DefenseAudit {
  rawItems: string[];
  tools: string;
  hasDeterministicMath: boolean;
  hasGrounding: boolean;
  isLowTemp: boolean;
}

export interface ParsedChatOutput {
  body: string;
  defense: DefenseAudit | null;
  sources: ChatSource[];
}

export function splitChatSources(
  content: string,
): ParsedChatOutput {
  let text = content;
  let sources: ChatSource[] = [];
  let defense: DefenseAudit | null = null;

  // 1. 출처 파싱
  const sourcesAt = text.lastIndexOf(SOURCES_HEADER);
  if (sourcesAt !== -1) {
    const rawSources = text.slice(sourcesAt + SOURCES_HEADER.length).split("\n");
    const parsedSources: ChatSource[] = [];
    let expectedIndex = 1;
    let valid = true;

    for (const line of rawSources) {
      if (line.trim() === "") continue;
      const m = SOURCE_ITEM_RE.exec(line.trim());
      if (!m || Number(m[1]) !== expectedIndex) {
        valid = false;
        break;
      }
      parsedSources.push({ index: Number(m[1]), source: m[2], passageId: m[3] });
      expectedIndex += 1;
    }

    if (valid && parsedSources.length > 0) {
      sources = parsedSources;
      text = text.slice(0, sourcesAt);
    }
  }

  // 2. 방어 증명 파싱
  const defenseAt = text.lastIndexOf(DEFENSE_HEADER);
  if (defenseAt !== -1) {
    const rawDefense = text.slice(defenseAt + DEFENSE_HEADER.length).split("\n");
    const items: string[] = [];

    for (const line of rawDefense) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      if (trimmed.startsWith("- ")) {
        items.push(trimmed.slice(2));
      }
    }

    if (items.length > 0) {
      const rawText = items.join("\n");
      const toolMatch = items.find((i) => i.includes("검색 도구"));
      const tools = toolMatch ? toolMatch.split(":")[1]?.trim() ?? "미사용" : "미사용";

      defense = {
        rawItems: items,
        tools,
        hasDeterministicMath: rawText.includes("결정론 계산기"),
        hasGrounding: rawText.includes("grounding") || rawText.includes("근거 문서"),
        isLowTemp: rawText.includes("저온 생성") || rawText.includes("temp"),
      };
      text = text.slice(0, defenseAt);
    }
  }

  return { body: text.trim(), defense, sources };
}

