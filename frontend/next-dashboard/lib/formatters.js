/*
 * KRW 금액/퍼센트/수량 포맷터
 * Streamlit의 formatters.py와 동일한 형식을 재현한다.
 */

export function formatKrw(value, signed = false) {
  const n = Number(value) || 0;
  const abs = Math.abs(n);
  const formatted = abs.toLocaleString("ko-KR", {
    maximumFractionDigits: 0,
  });
  if (signed && n > 0) return `+${formatted}`;
  if (n < 0) return `-${formatted}`;
  return formatted;
}

export function formatKrwCompact(value, signed = false) {
  const n = Number(value) || 0;
  const abs = Math.abs(n);
  let text;
  if (abs >= 1_0000_0000) {
    text = `${(abs / 1_0000_0000).toFixed(1)}억`;
  } else if (abs >= 1_0000) {
    text = `${(abs / 1_0000).toFixed(1)}만`;
  } else {
    text = abs.toLocaleString("ko-KR");
  }
  if (signed && n > 0) return `+${text}`;
  if (n < 0) return `-${text}`;
  return text;
}

export function formatPct(value, decimals = 2, signed = true) {
  const n = Number(value);
  if (Number.isNaN(n)) return "N/A";
  const text = Math.abs(n).toFixed(decimals);
  if (signed && n > 0) return `+${text}%`;
  if (n < 0) return `-${text}%`;
  return `${text}%`;
}

export function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n) || n === 0) return "0";
  return n.toFixed(8).replace(/0+$/, "").replace(/\.$/, "");
}
