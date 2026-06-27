/** catch 절의 unknown 에러에서 사람이 읽을 메시지를 뽑는다. 프론트 전역에서 반복되던 식. */
export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
