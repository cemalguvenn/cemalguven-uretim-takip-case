import { useEffect, useState } from "react";
import {
  App,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
} from "antd";
import dayjs from "dayjs";

import api from "../api/client.js";
import StatusTag from "./StatusTag.jsx";
import { SEVERITY_COLORS } from "../theme.js";

const STATIONS = ["IMM-2700-1", "IMM-2700-2", "IMM-2700-3", "IMM-4000-1", "IMM-4000-2"];
// metric groups with their unit suffix
const PCT_FIELDS = [
  ["availability", "A (Kullanılırlık)"],
  ["performance", "P (Performans)"],
  ["quality", "Q (Kalite)"],
  ["oee", "OEE"],
];
const MIN_FIELDS = [
  ["calisma_suresi", "Çalışma Süresi"],
  ["durus_suresi", "Duruş Süresi"],
  ["planli_durus", "Planlı Duruş"],
  ["plansiz_durus", "Plansız Duruş"],
];
const QTY_FIELDS = [
  ["uretilen_miktar", "Üretilen Miktar"],
  ["hatali_uretilen", "Hatalı Üretilen"],
];

export default function RecordDetailModal({ recordId, open, onClose, onChanged }) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [record, setRecord] = useState(null);
  const [errors, setErrors] = useState([]);
  const [audit, setAudit] = useState([]);
  const [saving, setSaving] = useState(false);

  const refresh = async () => {
    const [rec, errs, log] = await Promise.all([
      api.getRecord(recordId),
      api.getRecordErrors(recordId),
      api.getRecordAudit(recordId),
    ]);
    setRecord(rec.data);
    setErrors(errs.data);
    setAudit(log.data);
    form.setFieldsValue(rec.data);
  };

  useEffect(() => {
    if (open && recordId) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, recordId]);

  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.updateRecord(recordId, { ...values, reason: "Manuel düzeltme" });
      message.success("Kayıt düzeltildi ve yeniden doğrulandı.");
      await refresh();
      onChanged?.();
    } catch (err) {
      message.error(err.userMessage);
    } finally {
      setSaving(false);
    }
  };

  const act = async (action) => {
    try {
      await api.changeStatus(recordId, action, `UI: ${action}`);
      message.success("İşlem uygulandı.");
      await refresh();
      onChanged?.();
    } catch (err) {
      message.error(err.userMessage);
    }
  };

  const errorCols = [
    { title: "Seviye", dataIndex: "severity", width: 90, render: (s) => <Tag color={SEVERITY_COLORS[s]}>{s}</Tag> },
    { title: "Kural", dataIndex: "rule_code", width: 200 },
    { title: "Alan", dataIndex: "field_name", width: 130 },
    { title: "Mesaj", dataIndex: "message" },
    { title: "Beklenen", dataIndex: "expected_value", width: 110 },
    { title: "Mevcut", dataIndex: "actual_value", width: 110 },
  ];

  const footer = (
    <Space>
      <Popconfirm title="Bu kaydı reddet?" onConfirm={() => act("reject")}>
        <Button danger>Reddet</Button>
      </Popconfirm>
      {record?.is_hidden ? (
        <Button onClick={() => act("unhide")}>Gizlemeyi Kaldır</Button>
      ) : (
        <Button onClick={() => act("hide")}>Gizle</Button>
      )}
      {record?.status === "rejected" && <Button onClick={() => act("restore")}>Geri Al</Button>}
      <Button type="primary" loading={saving} onClick={save}>
        Kaydet & Doğrula
      </Button>
    </Space>
  );

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={900}
      footer={footer}
      title={
        record ? (
          <Space>
            <span>Kayıt #{record.record_id}</span>
            <StatusTag status={record.status} />
            {record.is_hidden && <Tag>Gizli</Tag>}
            <span style={{ color: "#8694a8", fontWeight: 400, fontSize: 13 }}>
              {record.tarih} · {record.is_istasyon_adi} · V{record.vardiya}
            </span>
          </Space>
        ) : (
          "Kayıt"
        )
      }
    >
      <Tabs
        items={[
          {
            key: "edit",
            label: "Düzelt",
            children: (
              <Form form={form} layout="vertical">
                <Row gutter={12}>
                  <Col span={10}>
                    <Form.Item name="stok_adi" label="Stok Adı">
                      <Input allowClear placeholder="Ürün adı" />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item name="is_istasyon_adi" label="İş İstasyon Adı">
                      <Select
                        allowClear showSearch placeholder="İstasyon seçin"
                        options={STATIONS.map((s) => ({ value: s, label: s }))}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item name="vardiya" label="Vardiya">
                      <Select
                        allowClear placeholder="Vardiya"
                        options={[
                          { value: 1, label: "Vardiya 1 — Sabah" },
                          { value: 2, label: "Vardiya 2 — Öğle" },
                          { value: 3, label: "Vardiya 3 — Gece" },
                        ]}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item name="is_emri_no" label="İş Emri No">
                      <Input allowClear />
                    </Form.Item>
                  </Col>

                  {PCT_FIELDS.map(([name, label]) => (
                    <Col span={4} key={name}>
                      <Form.Item name={name} label={label}>
                        <InputNumber style={{ width: "100%" }} suffix="%" step={0.1} />
                      </Form.Item>
                    </Col>
                  ))}
                  {MIN_FIELDS.map(([name, label]) => (
                    <Col span={6} key={name}>
                      <Form.Item name={name} label={label}>
                        <InputNumber style={{ width: "100%" }} addonAfter="dk" step={1} />
                      </Form.Item>
                    </Col>
                  ))}
                  {QTY_FIELDS.map(([name, label]) => (
                    <Col span={6} key={name}>
                      <Form.Item name={name} label={label}>
                        <InputNumber style={{ width: "100%" }} addonAfter="adet" step={1} precision={0} />
                      </Form.Item>
                    </Col>
                  ))}
                </Row>
              </Form>
            ),
          },
          {
            key: "errors",
            label: `Hatalar (${errors.length})`,
            children: (
              <Table
                rowKey="id"
                size="small"
                dataSource={errors}
                columns={errorCols}
                pagination={false}
              />
            ),
          },
          {
            key: "audit",
            label: `Geçmiş (${audit.length})`,
            children: (
              <List
                size="small"
                dataSource={audit}
                locale={{ emptyText: "Henüz değişiklik yok." }}
                renderItem={(a) => (
                  <List.Item>
                    <Space split="·" wrap>
                      <Tag>{a.action}</Tag>
                      {a.field_name && <span>{a.field_name}</span>}
                      {a.old_value !== null && (
                        <span style={{ color: "#8694a8" }}>
                          {a.old_value} → <b>{a.new_value}</b>
                        </span>
                      )}
                      <span style={{ color: "#6b7689" }}>
                        {dayjs(a.created_at).format("DD.MM HH:mm")}
                      </span>
                    </Space>
                  </List.Item>
                )}
              />
            ),
          },
        ]}
      />
    </Modal>
  );
}
