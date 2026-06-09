// Design tokens shared across the app (dark, enterprise look).
export const brandTheme = {
  colorPrimary: "#3b82f6",
  colorInfo: "#3b82f6",
  colorSuccess: "#22c55e",
  colorWarning: "#f59e0b",
  colorError: "#ef4444",
  borderRadius: 10,
  fontSize: 14,
  colorBgLayout: "#0f1420",
  colorBgContainer: "#171c2b",
  colorBorderSecondary: "#252b3b",
};

// Status → colour/label, used by tags and charts everywhere.
export const STATUS_META = {
  clean: { color: "success", label: "Temiz" },
  warning: { color: "warning", label: "Uyarı" },
  error: { color: "error", label: "Hata" },
  corrected: { color: "processing", label: "Düzeltildi" },
  rejected: { color: "default", label: "Reddedildi" },
  submitted: { color: "cyan", label: "Gönderildi" },
  pending: { color: "default", label: "Beklemede" },
  hidden: { color: "default", label: "Gizli" },
};

// Hex palette for Recharts (chart libs need raw colours, not antd tokens).
export const CHART_COLORS = {
  primary: "#3b82f6",
  success: "#22c55e",
  warning: "#f59e0b",
  error: "#ef4444",
  purple: "#a855f7",
  cyan: "#06b6d4",
  grid: "#252b3b",
  axis: "#7b8694",
};

export const SEVERITY_COLORS = {
  error: "#ef4444",
  warning: "#f59e0b",
  info: "#3b82f6",
};
