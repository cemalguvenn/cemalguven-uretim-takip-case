import { useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
} from "antd";
import { ReloadOutlined, UndoOutlined } from "@ant-design/icons";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";
import { SEVERITY_COLORS } from "../theme.js";

const SEVERITIES = ["error", "warning", "info"];

export default function Settings() {
  const { message, modal } = App.useApp();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    api.listRules().then((r) => setRules(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  // Persist a single field change and reflect it locally.
  const save = async (rule, patch) => {
    setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, ...patch } : r)));
    try {
      await api.updateRule(rule.id, patch);
    } catch (e) {
      message.error(e.userMessage);
      load(); // revert to server truth on failure
    }
  };

  const revalidate = async () => {
    setBusy(true);
    try {
      const r = await api.revalidateAll();
      modal.success({
        title: "Yeniden doğrulama tamamlandı",
        content: `Temiz: ${r.data.clean} · Uyarı: ${r.data.warning} · Hata: ${r.data.error}`,
      });
    } catch (e) {
      message.error(e.userMessage);
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      const r = await api.resetRules();
      setRules(r.data);
      message.success("Kurallar varsayılan değerlere sıfırlandı.");
    } catch (e) {
      message.error(e.userMessage);
    } finally {
      setBusy(false);
    }
  };

  const categories = [...new Set(rules.map((r) => r.category))].map((c) => ({
    text: c,
    value: c,
  }));

  const columns = [
    {
      title: "Kural",
      dataIndex: "display_name",
      render: (v, r) => (
        <div>
          <div>{v}</div>
          <div style={{ fontSize: 11, color: "#6b7689" }}>{r.rule_code}</div>
        </div>
      ),
    },
    {
      title: "Kategori",
      dataIndex: "category",
      width: 150,
      filters: categories,
      onFilter: (val, r) => r.category === val,
      render: (c) => <Tag>{c}</Tag>,
    },
    {
      title: "Seviye",
      dataIndex: "default_severity",
      width: 130,
      render: (sev, r) => (
        <Select
          size="small"
          value={sev}
          style={{ width: 110 }}
          onChange={(v) => save(r, { default_severity: v })}
          options={SEVERITIES.map((s) => ({
            value: s,
            label: <Tag color={SEVERITY_COLORS[s]}>{s}</Tag>,
          }))}
        />
      ),
    },
    {
      title: "Uyarı Eşiği",
      dataIndex: "warning_threshold",
      width: 130,
      render: (val, r) => (
        <InputNumber
          size="small"
          value={val}
          placeholder="—"
          style={{ width: 100 }}
          onChange={(v) =>
            setRules((prev) => prev.map((x) => (x.id === r.id ? { ...x, warning_threshold: v } : x)))
          }
          onBlur={() => save(r, { warning_threshold: r.warning_threshold })}
        />
      ),
    },
    {
      title: "Hata Eşiği",
      dataIndex: "error_threshold",
      width: 130,
      render: (val, r) => (
        <InputNumber
          size="small"
          value={val}
          placeholder="—"
          style={{ width: 100 }}
          onChange={(v) =>
            setRules((prev) => prev.map((x) => (x.id === r.id ? { ...x, error_threshold: v } : x)))
          }
          onBlur={() => save(r, { error_threshold: r.error_threshold })}
        />
      ),
    },
    {
      title: "Aktif",
      dataIndex: "is_active",
      width: 80,
      render: (active, r) => (
        <Switch checked={active} onChange={(v) => save(r, { is_active: v })} />
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Ayarlar — Validasyon Kuralları"
        subtitle="Eşik değerlerini, şiddeti ve aktifliği düzenleyin. Değişiklikler otomatik kaydedilir."
        extra={
          <Space>
            <Popconfirm title="Tüm kuralları varsayılana sıfırla?" onConfirm={reset}>
              <Button icon={<UndoOutlined />} disabled={busy}>
                Varsayılana Sıfırla
              </Button>
            </Popconfirm>
            <Button type="primary" icon={<ReloadOutlined />} loading={busy} onClick={revalidate}>
              Tüm Verileri Yeniden Doğrula
            </Button>
          </Space>
        }
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Eşik değişiklikleri mevcut kayıtlara hemen yansımaz."
        description="Bir veya birden fazla kuralı düzenledikten sonra 'Tüm Verileri Yeniden Doğrula' butonuna basın; kayıtlar güncel kurallara göre yeniden değerlendirilir."
      />

      <Card>
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={rules}
          columns={columns}
          pagination={false}
        />
      </Card>
    </>
  );
}
