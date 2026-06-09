// Small formatting helpers used across pages.

export const nf = new Intl.NumberFormat("tr-TR");

export function fmtNum(v) {
  if (v === null || v === undefined) return "—";
  return nf.format(v);
}

export function fmtPct(v, digits = 1) {
  if (v === null || v === undefined) return "—";
  return `${Number(v).toFixed(digits)}%`;
}

// Colour an OEE value by industrial bands (good / fair / poor).
export function oeeColor(v) {
  if (v === null || v === undefined) return "#8694a8";
  if (v >= 85) return "#22c55e";
  if (v >= 60) return "#f59e0b";
  return "#ef4444";
}
