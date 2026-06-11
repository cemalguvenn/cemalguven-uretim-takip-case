import { useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  UndoOutlined,
} from "@ant-design/icons";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";
import { SEVERITY_COLORS } from "../theme.js";

const SEVERITIES = ["error", "warning", "info"];

// Numeric fields a custom rule can target (mirrors backend validation.metadata).
const CUSTOM_FIELDS = [
  ["availability", "A (Kullanılabilirlik)"],
  ["performance", "P (Performans)"],
  ["quality", "Q (Kalite)"],
  ["oee", "OEE"],
  ["calisma_suresi", "Çalışma Süresi"],
  ["durus_suresi", "Duruş Süresi"],
  ["planli_durus", "Planlı Duruş"],
  ["plansiz_durus", "Plansız Duruş"],
  ["uretilen_miktar", "Üretilen Miktar"],
  ["hatali_uretilen", "Hatalı Üretilen"],
];

const NA = <span style={{ color: "#6b7689" }}>Uygulanmaz</span>;

export default function Settings() {
  const { message, modal } = App.useApp();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // Create/edit modal for custom rules.
  const [form] = Form.useForm();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = () => {
    setLoading(true);
    api.listRules().then((r) => setRules(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  // Persist a single field change (inline edit) and reflect it locally.
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
      message.success("Yerleşik kurallar varsayılana sıfırlandı.");
    } catch (e) {
      message.error(e.userMessage);
    } finally {
      setBusy(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (r) => {
    setEditing(r);
    form.setFieldsValue({
      display_name: r.display_name,
      description: r.description,
      target_field: r.target_field,
      comparison: r.comparison,
      default_severity: r.default_severity,
      warning_threshold: r.warning_threshold,
      error_threshold: r.error_threshold,
    });
    setModalOpen(true);
  };

  const submitModal = async () => {
    let vals;
    try {
      vals = await form.validateFields();
    } catch {
      return; // antd shows field errors
    }
    if (vals.warning_threshold == null && vals.error_threshold == null) {
      message.error("En az bir eşik (uyarı veya hata) belirtilmeli.");
      return;
    }
    try {
      if (editing) {
        await api.updateRule(editing.id, vals);
        message.success("Özel kural güncellendi.");
      } else {
        await api.createRule(vals);
        message.success("Özel kural oluşturuldu. Uygulamak için yeniden doğrulayın.");
      }
      setModalOpen(false);
      load();
    } catch (e) {
      message.error(e.userMessage || "Kaydedilemedi.");
    }
  };

  const remove = async (r) => {
    try {
      await api.deleteRule(r.id);
      message.success("Özel kural silindi.");
      load();
    } catch (e) {
      message.error(e.userMessage);
    }
  };

  const categories = [...new Set(rules.map((r) => r.category))].map((c) => ({
    text: c,
    value: c,
  }));

  // Inline threshold editor (shown only where the rule actually uses it).
  const thresholdInput = (field) => (val, r) => (
    <InputNumber
      size="small"
      value={val}
      placeholder="—"
      style={{ width: 100 }}
      onChange={(v) =>
        setRules((prev) => prev.map((x) => (x.id === r.id ? { ...x, [field]: v } : x)))
      }
      onBlur={() => save(r, { [field]: r[field] })}
    />
  );

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
      title: "Tür",
      dataIndex: "rule_type",
      width: 96,
      filters: [
        { text: "Yerleşik", value: "builtin" },
        { text: "Özel", value: "custom_range" },
      ],
      onFilter: (val, r) => r.rule_type === val,
      render: (t) =>
        t === "custom_range" ? <Tag color="geekblue">Özel</Tag> : <Tag>Yerleşik</Tag>,
    },
    {
      title: "Kategori",
      dataIndex: "category",
      width: 140,
      filters: categories,
      onFilter: (val, r) => r.category === val,
      render: (c) => <Tag>{c}</Tag>,
    },
    {
      title: "Seviye",
      dataIndex: "default_severity",
      width: 120,
      render: (sev, r) => (
        <Select
          size="small"
          value={sev}
          style={{ width: 100 }}
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
      width: 124,
      // Two-tier rules only.
      render: (val, r) => (r.threshold_kind === "dual" ? thresholdInput("warning_threshold")(val, r) : NA),
    },
    {
      title: "Hata Eşiği",
      dataIndex: "error_threshold",
      width: 124,
      // Any rule that uses a threshold (single or dual).
      render: (val, r) => (r.threshold_kind === "none" ? NA : thresholdInput("error_threshold")(val, r)),
    },
    {
      title: "Aktif",
      dataIndex: "is_active",
      width: 72,
      render: (active, r) => (
        <Switch checked={active} onChange={(v) => save(r, { is_active: v })} />
      ),
    },
    {
      title: "",
      width: 84,
      render: (_, r) =>
        r.rule_type === "custom_range" ? (
          <Space size={0}>
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
            <Popconfirm title="Bu özel kuralı sil?" onConfirm={() => remove(r)}>
              <Button type="text" size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        ) : (
          <Tooltip title="Yerleşik kurallar silinemez; devre dışı bırakabilirsiniz.">
            <Button type="text" size="small" disabled icon={<DeleteOutlined />} />
          </Tooltip>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Ayarlar — Validasyon Kuralları"
        subtitle="Eşik, şiddet ve aktifliği düzenleyin; kendi özel kurallarınızı oluşturun. Değişiklikler otomatik kaydedilir."
        extra={
          <Space>
            <Button icon={<PlusOutlined />} onClick={openCreate} disabled={busy}>
              Yeni Kural
            </Button>
            <Popconfirm title="Yerleşik kuralları varsayılana sıfırla?" onConfirm={reset}>
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
        message="Eşik/kural değişiklikleri mevcut kayıtlara hemen yansımaz."
        description="Bir veya birden fazla kuralı düzenledikten ya da yeni kural ekledikten sonra 'Tüm Verileri Yeniden Doğrula' butonuna basın; kayıtlar güncel kurallara göre yeniden değerlendirilir."
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

      <Modal
        title={editing ? "Özel Kuralı Düzenle" : "Yeni Özel Kural"}
        open={modalOpen}
        onOk={submitModal}
        onCancel={() => setModalOpen(false)}
        okText={editing ? "Kaydet" : "Oluştur"}
        cancelText="İptal"
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ comparison: "max", default_severity: "warning" }}
        >
          <Form.Item
            name="display_name"
            label="Kural Adı"
            rules={[{ required: true, message: "Ad gerekli." }]}
          >
            <Input placeholder="Örn. OEE çok yüksek" />
          </Form.Item>
          <Form.Item
            name="target_field"
            label="Alan"
            rules={[{ required: true, message: "Alan seçin." }]}
          >
            <Select
              placeholder="Kontrol edilecek sayısal alan"
              options={CUSTOM_FIELDS.map(([v, l]) => ({ value: v, label: l }))}
            />
          </Form.Item>
          <Form.Item name="comparison" label="Koşul" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "max", label: "Üst sınır — değer eşiği AŞARSA işaretle" },
                { value: "min", label: "Alt sınır — değer eşiğin ALTINDAYSA işaretle" },
              ]}
            />
          </Form.Item>
          <Space size="large" align="start">
            <Form.Item name="warning_threshold" label="Uyarı Eşiği">
              <InputNumber style={{ width: 150 }} placeholder="opsiyonel" />
            </Form.Item>
            <Form.Item name="error_threshold" label="Hata Eşiği">
              <InputNumber style={{ width: 150 }} placeholder="opsiyonel" />
            </Form.Item>
          </Space>
          <Form.Item
            name="default_severity"
            label="Şiddet"
            extra="Yalnızca tek eşik girildiğinde kullanılır (iki eşik varsa uyarı/hata otomatik)."
          >
            <Select options={SEVERITIES.map((s) => ({ value: s, label: s }))} />
          </Form.Item>
          <Form.Item name="description" label="Açıklama">
            <Input.TextArea rows={2} placeholder="opsiyonel" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
