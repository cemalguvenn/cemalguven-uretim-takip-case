// Consistent dark tooltip for all Recharts charts. Formats OEE/percent series
// with a "%" suffix and others with tr-TR number grouping.
//
// Optional props (default to prior behavior so existing usages are unaffected):
//   hideKeys    — dataKeys to drop (e.g. a transparent waterfall "base" spacer)
//   percentKeys — extra dataKeys to render as "X.X%"
const PCT_KEYS = new Set(["avg_oee", "OEE", "oee"]);

function fmt(entry, percentKeys) {
  const v = entry.value;
  if (v === null || v === undefined) return "—";
  if (PCT_KEYS.has(entry.dataKey) || percentKeys.includes(entry.dataKey))
    return `${Number(v).toFixed(1)}%`;
  return Number(v).toLocaleString("tr-TR");
}

export default function ChartTooltip({
  active,
  payload,
  label,
  hideKeys = [],
  percentKeys = [],
}) {
  if (!active || !payload || payload.length === 0) return null;
  const rows = payload.filter((p) => !hideKeys.includes(p.dataKey));
  if (rows.length === 0) return null;
  return (
    <div
      style={{
        background: "#11161f",
        border: "1px solid #2b3346",
        borderRadius: 8,
        padding: "8px 12px",
        boxShadow: "0 6px 18px rgba(0,0,0,0.45)",
      }}
    >
      {label != null && (
        <div style={{ color: "#8694a8", fontSize: 12, marginBottom: 6 }}>{label}</div>
      )}
      {rows.map((p) => (
        <div
          key={p.dataKey}
          style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: p.color || p.fill || p.payload?.fill,
              flex: "none",
            }}
          />
          <span style={{ color: "#c7cdda" }}>{p.name}</span>
          <b style={{ marginLeft: "auto", color: "#fff" }}>{fmt(p, percentKeys)}</b>
        </div>
      ))}
    </div>
  );
}
