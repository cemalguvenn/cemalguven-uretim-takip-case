import { useEffect, useState } from "react";
import { Alert, Card, Col, DatePicker, Row, Spin, Statistic, Table } from "antd";
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";
import ChartTooltip from "../components/ChartTooltip.jsx";
import { CHART_COLORS } from "../theme.js";
import { oeeColor } from "../utils/format.js";

const { RangePicker } = DatePicker;

const tip = {
  background: "#11161f",
  border: "1px solid #2b3346",
  borderRadius: 8,
  color: "#e6e9ef",
};

export default function LossAnalysis() {
  const [range, setRange] = useState(null);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    const params = range
      ? { start: range[0].format("YYYY-MM-DD"), end: range[1].format("YYYY-MM-DD") }
      : {};
    setLoading(true);
    api.lossAnalysis(params).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [range]);

  // Build the floating waterfall: each step has a transparent "base" + a visible
  // colored segment, so bars appear to descend from 100% to OEE.
  const waterfall = data
    ? (() => {
        const steps = [
          { name: "Maks.", base: 0, value: 100, fill: "#475569" },
          { name: "Kullanılabilirlik Kaybı", base: 100 - data.availability_loss, value: data.availability_loss, fill: CHART_COLORS.error },
          { name: "Performans Kaybı", base: data.availability - data.performance_loss, value: data.performance_loss, fill: CHART_COLORS.warning },
          { name: "Kalite Kaybı", base: data.oee, value: data.quality_loss, fill: CHART_COLORS.purple },
          { name: "OEE", base: 0, value: data.oee, fill: CHART_COLORS.success },
        ];
        return steps;
      })()
    : [];

  const downtime = data
    ? [
        { name: "Planlı Duruş", value: data.planned_stop_min },
        { name: "Plansız Duruş", value: data.unplanned_stop_min },
        { name: "Çalışma", value: data.run_min },
      ]
    : [];
  const DOWNTIME_HEX = ["#f59e0b", "#ef4444", "#22c55e"];

  const stationCols = [
    { title: "İstasyon", dataIndex: "istasyon" },
    { title: "A", dataIndex: "availability", render: (v) => `${v}%` },
    { title: "P", dataIndex: "performance", render: (v) => `${v}%` },
    { title: "Q", dataIndex: "quality", render: (v) => `${v}%` },
    {
      title: "OEE", dataIndex: "oee",
      render: (v) => <b style={{ color: oeeColor(v) }}>{v}%</b>,
      sorter: (a, b) => a.oee - b.oee,
    },
    { title: "Kullanılabilirlik Kaybı", dataIndex: "availability_loss", render: (v) => `${v}%` },
    { title: "Performans Kaybı", dataIndex: "performance_loss", render: (v) => `${v}%` },
    { title: "Kalite Kaybı", dataIndex: "quality_loss", render: (v) => `${v}%` },
  ];

  return (
    <Spin spinning={loading}>
      <PageHeader
        title="Kayıp Analizi (OEE Waterfall)"
        subtitle="OEE'nin nerede kaybedildiği — kullanılabilirlik / performans / kalite kayıpları"
        extra={<RangePicker onChange={setRange} allowClear />}
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Not: P>100 olan kayıtlar (yanlış ideal çevrim süresi kaynaklı veri artefaktı) waterfall'da %100'e sınırlanır."
      />

      {data && (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={6}>
              <Card className="kpi-card">
                <Statistic title="Kullanılabilirlik (A)" value={data.availability} suffix="%" />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="kpi-card">
                <Statistic title="Performans (P)" value={data.performance} suffix="%" />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="kpi-card">
                <Statistic title="Kalite (Q)" value={data.quality} suffix="%" />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="kpi-card">
                <Statistic title="OEE" value={data.oee} suffix="%" valueStyle={{ color: oeeColor(data.oee) }} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={15}>
              <Card title="OEE Kayıp Şelalesi" styles={{ body: { height: 360 } }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={waterfall} margin={{ top: 10, right: 16, bottom: 30, left: -10 }}>
                    <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
                    <XAxis dataKey="name" stroke={CHART_COLORS.axis} tick={{ fontSize: 11 }} angle={-12} textAnchor="end" interval={0} height={50} />
                    <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 12 }} domain={[0, 100]} unit="%" />
                    <Tooltip
                      contentStyle={tip}
                      formatter={(v, n) => (n === "value" ? [`${Number(v).toFixed(1)}%`, "Değer"] : null)}
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    />
                    <Bar dataKey="base" stackId="w">
                      {waterfall.map((s, i) => (
                        <Cell key={`b${i}`} fill="transparent" />
                      ))}
                    </Bar>
                    <Bar dataKey="value" stackId="w" radius={[6, 6, 0, 0]}>
                      {waterfall.map((s, i) => (
                        <Cell key={`v${i}`} fill={s.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>

            <Col xs={24} lg={9}>
              <Card title="Süre Dağılımı (dakika)" styles={{ body: { height: 360 } }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={downtime} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
                      {downtime.map((_, i) => (
                        <Cell key={i} fill={DOWNTIME_HEX[i]} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>

          <Card title="İstasyon Bazlı Kayıplar" style={{ marginTop: 16 }}>
            <Table
              rowKey="istasyon"
              size="small"
              dataSource={data.stations}
              columns={stationCols}
              pagination={false}
            />
          </Card>
        </>
      )}
    </Spin>
  );
}
