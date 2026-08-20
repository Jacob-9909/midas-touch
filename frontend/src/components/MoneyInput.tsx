"use client";

/** 큰 원화 숫자 입력. 네이티브 `<input type="number">`는 타이핑 중 1,000단위 콤마를 못 보여줘서
 * text + inputMode="numeric"으로 직접 포맷한다. 표시는 콤마 포함, 값은 콤마 뺀 순수 숫자. */
export function MoneyInput({
  value,
  onChange,
  className = "",
}: {
  value: number;
  onChange: (n: number) => void;
  className?: string;
}) {
  return (
    <input
      type="text"
      inputMode="numeric"
      value={value.toLocaleString("ko-KR")}
      onChange={(e) => {
        const digits = e.target.value.replace(/[^0-9]/g, "");
        onChange(digits === "" ? 0 : Number(digits));
      }}
      className={`font-mono-spec tabular-nums ${className}`}
    />
  );
}
