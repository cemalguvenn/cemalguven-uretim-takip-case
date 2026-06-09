import { useEffect, useState } from "react";
import { App, Button, Card, Col, Row, Select, Space, Statistic, Table, Tag } from "antd";
import { SettingOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";
import RecordDetailModal from "../components/RecordDetailModal.jsx";
import ExportMenu from "../components/ExportMenu.jsx";
import { SEVERITY_COLORS } from "../theme.js";
import { downloadCsv, downloadPdf } from "../utils/export.js";

const PDF_COLUMNS = [
  { key: "record_id", label: "Kayıt" },
  { key: "severity", label: "Seviye" },
  { key: "category", label: "Kategori" },
  { key: "rule_code", label: "Kural" },
  { key: "field_name", label: "Alan" },
  { key: "message", label: "Mesaj" },
  { key: "expected_value", label: "Beklenen" },
  { key: "actual_value", label: "Mevcut" },
  { key: "suggested_action", label: "Aksiyon" },
];

const CATEGORY_HEX = [
  "#3b82f6", "#ef4444", "#f59e0b", "#22c55e", "#a855f7", "#06b6d4", "#ec4899",
];

const tooltipStyle = {
  background: "#11161f",
  border: "1px solid #2b3346",
  borderRadius: 8,
  color: "#e6e9ef",
};

export default function ValidationReport() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState({ severity: null, category: null, rule_code: null });
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState({ open: false, id: null });

  useEffect(() => {
    api.validationSummary().then((r) => setSummary(r.data));
  }, []);

  const load = () => {
    setLoading(true);
    api
      .listErrors({ page, page_size: 50, ...filters })
      .then((r) => setData(r.data))
      .catch((e) => message.error(e.userMessage))
      .finally(() => setLoading(false));
  };
  useEffect(load, [page, filters]); // eslint-disable-line react-hooks/exhaustive-deps

  const sev = Object.fromEntries((summary?.by_severity || []).map((x) => [x.key, x.count]));
  const catData = (summary?.by_category || []).map((c) => ({ name: c.key, value: c.count }));
  const ruleOptions = (summary?.by_rule || []).map((r) => ({
    value: r.key,
    label: `${r.key} (${r.count})`,
  }));

  const setF = (patch) => {
    setFilters((p) => ({ ...p, ...patch }));
    setPage(1);
  };

  const fetchAllErrors = async () => {
    const all = [];
    let p = 1;
    while (true) {
      const r = await api.listErrors({ ...filters, page: p, page_size: 500 });
      all.push(...r.data.items);
      if (all.length >= r.data.total || r.data.items.length === 0) break;
      p += 1;
    }
    return all;
  };

  const exportCsv = async () => {
    const all = await fetchAllErrors();
    downloadCsv("validasyon_raporu.csv", all);
    message.success(`${all.length} hata kaydı indirildi.`);
  };

  const exportPdf = async () => {
    const all = await fetchAllErrors();
    downloadPdf("validasyon_raporu.pdf", "Validasyon Raporu", PDF_COLUMNS, all);
    message.success(`${all.length} hata kaydı PDF olarak indirildi.`);
  };

  const columns = [
    { title: "Kayıt", dataIndex: "record_id", width: 80 },
    {
      title: "Seviye", dataIndex: "severity", width: 100,
      render: (s) => <Tag color={SEVERITY_COLORS[s]}>{s}</Tag>,
    },
    { title: "Kategori", dataIndex: "category", width: 140 },
    { title: "Kural", dataIndex: "rule_code", width: 210 },
    { title: "Alan", dataIndex: "field_name", width: 130 },
    { title: "Mesaj", dataIndex: "message", ellipsis: true },
    { title: "Beklenen", dataIndex: "expected_value", width: 100 },
    { title: "Mevcut", dataIndex: "actual_value", width: 100 },
    { title: "Aksiyon", dataIndex: "suggested_action", width: 90, render: (a) => <Tag>{a}</Tag> },
    {
      title: "", key: "act", width: 70, fixed: "right",
      render: (_, row) => (
        <Button size="small" onClick={() => setModal({ open: true, id: row.record_id })}>
          Detay
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Validasyon Raporu"
        subtitle="Tespit edilen veri kalitesi sorunları — sınıflandırılmış ve gerekçeli"
        extra={
          <Space>
            <Button icon={<SettingOutlined />} onClick={() => navigate("/settings")}>
              Kuralları Yönet
            </Button>
            <ExportMenu onCsv={exportCsv} onPdf={exportPdf} />
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8} lg={5}>
          <Card className="kpi-card">
            <Statistic title="Toplam Bulgu" value={summary?.total ?? "—"} />
          </Card>
        </Col>
        <Col xs={24} sm={8} lg={5}>
          <Card className="kpi-card">
            <Statistic title="Hata" value={sev.error || 0} valueStyle={{ color: "#ef4444" }} />
          </Card>
        </Col>
        <Col xs={24} sm={8} lg={5}>
          <Card className="kpi-card">
            <Statistic title="Uyarı" value={sev.warning || 0} valueStyle={{ color: "#f59e0b" }} />
          </Card>
        </Col>
        <Col xs={24} sm={8} lg={5}>
          <Card className="kpi-card">
            <Statistic title="Bilgi" value={sev.info || 0} valueStyle={{ color: "#3b82f6" }} />
          </Card>
        </Col>
        <Col xs={24} lg={4}>
          <Card className="kpi-card">
            <Statistic title="Hata Tipi Sayısı" value={summary?.by_rule?.length || 0} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}>
          <Card title="Kategori Dağılımı" styles={{ body: { height: 300 } }}>
            {catData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={catData} dataKey="value" nameKey="name" outerRadius={95} innerRadius={55} paddingAngle={2}>
                    {catData.map((_, i) => (
                      <Cell key={i} fill={CATEGORY_HEX[i % CATEGORY_HEX.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : null}
          </Card>
        </Col>

        <Col xs={24} lg={16}>
          <Card
            title="Hata Listesi"
            extra={
              <Space wrap>
                <Select
                  allowClear placeholder="Seviye" style={{ width: 120 }}
                  options={["error", "warning", "info"].map((s) => ({ value: s, label: s }))}
                  onChange={(v) => setF({ severity: v })}
                />
                <Select
                  allowClear placeholder="Kategori" style={{ width: 150 }}
                  options={catData.map((c) => ({ value: c.name, label: c.name }))}
                  onChange={(v) => setF({ category: v })}
                />
                <Select
                  allowClear showSearch placeholder="Kural" style={{ width: 200 }}
                  options={ruleOptions}
                  optionFilterProp="label"
                  onChange={(v) => setF({ rule_code: v })}
                />
              </Space>
            }
          >
            <Table
              rowKey="id"
              size="small"
              loading={loading}
              dataSource={data.items}
              columns={columns}
              scroll={{ x: 1100 }}
              pagination={{
                current: page, pageSize: 50, total: data.total,
                showTotal: (t) => `Toplam ${t}`,
                onChange: setPage,
              }}
            />
          </Card>
        </Col>
      </Row>

      <RecordDetailModal
        recordId={modal.id}
        open={modal.open}
        onClose={() => setModal({ open: false, id: null })}
        onChanged={load}
      />
    </>
  );
}
