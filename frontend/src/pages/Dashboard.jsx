import { useEffect, useState } from "react";
import {
  Card,
  Col,
  DatePicker,
  Empty,
  Row,
  Spin,
  Statistic,
  Tooltip as AntTooltip,
} from "antd";
import {
  DashboardOutlined,
  FieldTimeOutlined,
  InboxOutlined,
  WarningOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  Legend,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";
import ChartTooltip from "../components/ChartTooltip.jsx";
import { CHART_COLORS, STATUS_META } from "../theme.js";
import { fmtNum, fmtPct, oeeColor } from "../utils/format.js";

const { RangePicker } = DatePicker;

const ChartCard = ({ title, extra, children }) => (
  <Card className="chart-card" title={title} extra={extra} styles={{ body: { height: 320 } }}>
    {children}
  </Card>
);

export default function Dashboard() {
  const navigate = useNavigate();
  const [range, setRange] = useState(null);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ summary: null, trend: [], shifts: [], stations: [] });

  useEffect(() => {
    const params = range
      ? { start: range[0].format("YYYY-MM-DD"), end: range[1].format("YYYY-MM-DD") }
      : {};
    setLoading(true);
    Promise.all([
      api.summary(params),
      api.oeeTrend(params),
      api.shiftComparison(params),
      api.stationRanking(params),
    ])
      .then(([s, t, sh, st]) =>
        setData({ summary: s.data, trend: t.data, shifts: sh.data, stations: st.data })
      )
      .finally(() => setLoading(false));
  }, [range]);

  const { summary, trend, shifts, stations } = data;
  const sc = summary?.status_counts || {};
  const totalRecords = Object.entries(sc)
    .filter(([k]) => k !== "hidden")
    .reduce((a, [, v]) => a + v, 0);
  const cleanRatio = totalRecords
    ? ((sc.clean || 0) / totalRecords) * 100
    : null;

  const trendData = trend.map((p) => ({ ...p, label: dayjs(p.tarih).format("DD MMM") }));
  const shiftData = shifts.map((s) => ({
    name: `V${s.vardiya}`,
    OEE: s.avg_oee,
    Üretim: s.production,
  }));
  const stationData = [...stations]
    .sort((a, b) => (a.avg_oee || 0) - (b.avg_oee || 0))
    .map((s) => ({ name: s.istasyon, OEE: s.avg_oee }));

  const qualityData = ["clean", "warning", "error", "corrected", "rejected"]
    .map((k) => ({ name: STATUS_META[k].label, key: k, value: sc[k] || 0 }))
    .filter((d) => d.value > 0);
  const QUALITY_HEX = {
    clean: "#22c55e",
    warning: "#f59e0b",
    error: "#ef4444",
    corrected: "#3b82f6",
    rejected: "#6b7280",
  };

  const kpi = (title, value, suffix, icon, color, footer = null) => (
    <Card className="kpi-card" styles={{ body: { padding: "18px 20px" } }}>
      <Statistic
        title={
          <span>
            {icon} {title}
          </span>
        }
        value={value ?? "—"}
        suffix={suffix}
        valueStyle={{ color, fontWeight: 600 }}
      />
      {footer}
    </Card>
  );

  // Defect rows excluded from metrics (defect > production) — surfaced so "0
  // fire" isn't misread as "no defects".
  const quarUnits = summary?.quarantined_defect_units || 0;
  const fireFooter =
    quarUnits > 0 ? (
      <AntTooltip title="Hatalı üretim > toplam üretim olduğu için karantinada — düzeltildiğinde metriklere dahil olur.">
        <div
          onClick={() => navigate("/records?status=error")}
          style={{ marginTop: 6, fontSize: 12, color: "#f59e0b", cursor: "pointer" }}
        >
          +{fmtNum(quarUnits)} fire · {fmtNum(summary.quarantined_defect_records)} kayıt
          karantinada
        </div>
      </AntTooltip>
    ) : null;

  return (
    <Spin spinning={loading}>
      <PageHeader
        title="Üretim Performans Dashboard"
        subtitle="Yalnızca doğrulanmış (temiz/uyarı/düzeltilmiş) kayıtlar metriklere dahildir"
        extra={<RangePicker onChange={setRange} allowClear />}
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={5}>
          {kpi(
            "Ort. OEE",
            summary ? Number(summary.avg_oee ?? 0).toFixed(1) : "—",
            "%",
            <DashboardOutlined />,
            oeeColor(summary?.avg_oee)
          )}
        </Col>
        <Col xs={24} sm={12} lg={5}>
          {kpi("Toplam Üretim", fmtNum(summary?.total_production), "adet", <InboxOutlined />, "#e6e9ef")}
        </Col>
        <Col xs={24} sm={12} lg={5}>
          {kpi("Toplam Fire", fmtNum(summary?.total_defect), "adet", <WarningOutlined />, "#f59e0b", fireFooter)}
        </Col>
        <Col xs={24} sm={12} lg={5}>
          {kpi(
            "Toplam Duruş",
            fmtNum(summary ? Math.round(summary.total_stop_minutes) : null),
            "dk",
            <FieldTimeOutlined />,
            "#e6e9ef"
          )}
        </Col>
        <Col xs={24} sm={12} lg={4}>
          {kpi(
            "Temiz Oran",
            cleanRatio !== null ? cleanRatio.toFixed(0) : "—",
            "%",
            <CheckCircleOutlined />,
            "#22c55e"
          )}
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <ChartCard title="OEE Trendi (Günlük)">
            {trendData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 10, right: 16, bottom: 0, left: -10 }}>
                  <defs>
                    <linearGradient id="oeeFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_COLORS.primary} stopOpacity={0.5} />
                      <stop offset="100%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
                  <XAxis dataKey="label" stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} />
                  <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} domain={[0, 100]} />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: CHART_COLORS.primary, strokeOpacity: 0.25 }} />
                  <ReferenceLine y={85} stroke={CHART_COLORS.success} strokeDasharray="4 4" label={{ value: "Hedef 85", fill: CHART_COLORS.success, fontSize: 11, position: "right" }} />
                  <Area type="monotone" name="OEE" dataKey="avg_oee" stroke={CHART_COLORS.primary} strokeWidth={2.5} fill="url(#oeeFill)" animationDuration={700} animationEasing="ease-out" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <Empty />
            )}
          </ChartCard>
        </Col>

        <Col xs={24} lg={8}>
          <ChartCard title="Kayıt Kalite Dağılımı">
            {qualityData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={qualityData} dataKey="value" nameKey="name"
                    innerRadius={60} outerRadius={95} paddingAngle={2} animationDuration={700}
                    onClick={(d) => d?.key && navigate(`/records?status=${d.key}`)}
                    style={{ cursor: "pointer" }}
                  >
                    {qualityData.map((d) => (
                      <Cell key={d.key} fill={QUALITY_HEX[d.key]} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Empty />
            )}
          </ChartCard>
        </Col>

        <Col xs={24} lg={12}>
          <ChartCard title="Vardiya Karşılaştırma">
            {shiftData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={shiftData} margin={{ top: 10, right: 16, bottom: 0, left: -10 }}>
                  <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
                  <XAxis dataKey="name" stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} />
                  <YAxis yAxisId="l" stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} domain={[0, 100]} />
                  <YAxis yAxisId="r" orientation="right" stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar
                    yAxisId="l" name="OEE" dataKey="OEE" fill={CHART_COLORS.primary}
                    radius={[6, 6, 0, 0]} maxBarSize={48} animationDuration={700}
                    onClick={(d) => d?.name && navigate(`/records?vardiya=${String(d.name).replace("V", "")}`)}
                    style={{ cursor: "pointer" }}
                  />
                  <Bar yAxisId="r" name="Üretim" dataKey="Üretim" fill={CHART_COLORS.cyan} radius={[6, 6, 0, 0]} maxBarSize={48} animationDuration={700} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty />
            )}
          </ChartCard>
        </Col>

        <Col xs={24} lg={12}>
          <ChartCard title="İstasyon OEE Sıralaması">
            {stationData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart layout="vertical" data={stationData} margin={{ top: 10, right: 24, bottom: 0, left: 20 }}>
                  <CartesianGrid stroke={CHART_COLORS.grid} horizontal={false} />
                  <XAxis type="number" stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} domain={[0, 100]} />
                  <YAxis type="category" dataKey="name" stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} width={92} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                  <Bar
                    name="OEE" dataKey="OEE" radius={[0, 6, 6, 0]} maxBarSize={28} animationDuration={700}
                    onClick={(d) => d?.name && navigate(`/records?istasyon=${encodeURIComponent(d.name)}`)}
                    style={{ cursor: "pointer" }}
                  >
                    {stationData.map((d, i) => (
                      <Cell key={i} fill={oeeColor(d.OEE)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty />
            )}
          </ChartCard>
        </Col>
      </Row>
    </Spin>
  );
}
