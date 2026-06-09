import { useEffect, useMemo, useState } from "react";
import {
  App,
  Button,
  Card,
  InputNumber,
  Modal,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";
import {
  CheckCircleFilled,
  CloseCircleFilled,
  CloudUploadOutlined,
  MinusCircleFilled,
  SendOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";

const { Text } = Typography;

const STATUS_VIEW = {
  success: { color: "#22c55e", icon: <CheckCircleFilled />, label: "Gönderildi" },
  failed: { color: "#ef4444", icon: <CloseCircleFilled />, label: "Hata" },
  skipped: { color: "#6b7280", icon: <MinusCircleFilled />, label: "Atlandı" },
  none: { color: "#3b82f6", icon: <CloudUploadOutlined />, label: "Hazır" },
};

export default function SyncManager() {
  const { message, modal } = App.useApp();
  const [cells, setCells] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [auto, setAuto] = useState({ enabled: false, interval_minutes: 60 });
  const [preview, setPreview] = useState({ open: false, cell: null, data: null });

  const load = async () => {
    setLoading(true);
    try {
      const [p, h, a] = await Promise.all([
        api.syncPending(),
        api.syncHistory(),
        api.getAutoSync(),
      ]);
      setCells(p.data);
      setHistory(h.data);
      setAuto(a.data);
    } finally {
      setLoading(false);
    }
  };

  const saveAuto = async (patch) => {
    const next = { ...auto, ...patch };
    setAuto(next);
    try {
      await api.setAutoSync(next);
      message.success(next.enabled ? "Otomatik gönderim açık." : "Otomatik gönderim kapalı.");
    } catch (e) {
      message.error(e.userMessage);
    }
  };

  const runNow = async () => {
    setSending(true);
    try {
      const r = await api.runSyncNow();
      message.success(r.data.message);
      await load();
    } finally {
      setSending(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  // Group cells into rows keyed by date, columns by shift.
  const rows = useMemo(() => {
    const byDate = {};
    cells.forEach((c) => {
      byDate[c.production_date] = byDate[c.production_date] || { date: c.production_date };
      byDate[c.production_date][`v${c.shift}`] = c;
    });
    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
  }, [cells]);

  const readyCount = cells.filter((c) => c.sync_status === "none" && !c.skip_reason).length;

  const openPreview = async (cell) => {
    setPreview({ open: true, cell, data: null });
    const r = await api.syncPreview(cell.production_date, cell.shift);
    setPreview({ open: true, cell, data: r.data });
  };

  const doSubmit = async (cell, force = false) => {
    const r = await api.syncSubmit(cell.production_date, cell.shift, force);
    const res = r.data;
    if (res.status === "success") message.success(`${cell.production_date} V${cell.shift}: ${res.message}`);
    else if (res.status === "duplicate")
      modal.confirm({
        title: "Zaten gönderilmiş",
        content: res.message,
        okText: "Yeniden Gönder",
        onOk: () => doSubmit(cell, true),
      });
    else message.warning(`${cell.production_date} V${cell.shift}: ${res.message}`);
    await load();
    return res;
  };

  const sendAllReady = async () => {
    setSending(true);
    const ready = cells.filter((c) => c.sync_status === "none" && !c.skip_reason);
    let ok = 0;
    for (const cell of ready) {
      const r = await api.syncSubmit(cell.production_date, cell.shift, false);
      if (r.data.status === "success") ok += 1;
      await new Promise((res) => setTimeout(res, 1000)); // rate-limit spacing
    }
    setSending(false);
    message.success(`${ok}/${ready.length} gönderim başarılı.`);
    load();
  };

  const Cell = ({ cell }) => {
    if (!cell) return <Text type="secondary">—</Text>;
    const view = STATUS_VIEW[cell.sync_status] || STATUS_VIEW.none;
    const disabled = cell.skip_reason || cell.total_production_units === 0;
    return (
      <Tooltip title={cell.skip_reason || `${cell.clean_count} temiz kayıt`}>
        <button
          onClick={() => !disabled && openPreview(cell)}
          disabled={disabled}
          style={{
            width: "100%",
            textAlign: "left",
            background: "transparent",
            border: `1px solid ${view.color}55`,
            borderLeft: `3px solid ${view.color}`,
            borderRadius: 8,
            padding: "8px 10px",
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.45 : 1,
            color: "#e6e9ef",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: view.color }}>
            {view.icon}
            <span style={{ fontSize: 12 }}>{view.label}</span>
            {cell.submission_id && <span style={{ fontSize: 11, opacity: 0.7 }}>#{cell.submission_id}</span>}
          </div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            OEE <b>{cell.oe_value ?? "—"}</b> · {cell.total_production_units.toLocaleString("tr-TR")} adet
          </div>
          <div style={{ fontSize: 11, color: "#8694a8" }}>
            {cell.clean_count} kayıt · {cell.machine_count} makine
          </div>
        </button>
      </Tooltip>
    );
  };

  const shiftCol = (n, title) => ({
    title,
    key: `v${n}`,
    width: 200,
    render: (_, row) => <Cell cell={row[`v${n}`]} />,
  });

  const matrixCols = [
    {
      title: "Tarih",
      dataIndex: "date",
      width: 130,
      fixed: "left",
      render: (d) => <b>{dayjs(d).format("DD MMM YYYY")}</b>,
    },
    shiftCol(1, "Vardiya 1 — Sabah"),
    shiftCol(2, "Vardiya 2 — Öğle"),
    shiftCol(3, "Vardiya 3 — Gece"),
  ];

  const historyCols = [
    { title: "Tarih", dataIndex: "production_date", width: 110 },
    { title: "V", dataIndex: "shift", width: 50 },
    { title: "OEE", dataIndex: "oe_value", width: 80 },
    { title: "Üretim", dataIndex: "total_production", width: 90, render: (v) => v?.toLocaleString("tr-TR") },
    { title: "Makine", dataIndex: "machine_count", width: 80 },
    {
      title: "Durum", dataIndex: "status", width: 120,
      render: (s) => {
        const v = STATUS_VIEW[s === "success" ? "success" : "failed"];
        return <Tag color={s === "success" ? "success" : "error"}>{s}</Tag>;
      },
    },
    { title: "HTTP", dataIndex: "response_status", width: 70 },
    { title: "Sub#", dataIndex: "submission_id", width: 70 },
    { title: "Deneme", dataIndex: "attempt_count", width: 80 },
    {
      title: "Zaman", dataIndex: "last_attempt_at", width: 150,
      render: (v) => (v ? dayjs(v).format("DD.MM HH:mm:ss") : "—"),
    },
  ];

  return (
    <>
      <PageHeader
        title="API Gönderim"
        subtitle="Doğrulanmış veri, gün × vardiya bazında hedef sisteme gönderilir (yalnızca temiz kayıtlar)"
        extra={
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={sending}
            disabled={readyCount === 0}
            onClick={sendAllReady}
          >
            Tüm Hazır Verileri Gönder ({readyCount})
          </Button>
        }
      />

      <Card style={{ marginBottom: 16 }}>
        <Space size="large" wrap>
          <Space size={8}>
            <Switch checked={auto.enabled} onChange={(v) => saveAuto({ enabled: v })} />
            <span>Otomatik gönderim (her vardiya sonrası)</span>
          </Space>
          <Space size={8}>
            <span style={{ color: "#8694a8" }}>Aralık (dk):</span>
            <InputNumber
              min={1}
              max={1440}
              value={auto.interval_minutes}
              onChange={(v) => v && setAuto({ ...auto, interval_minutes: v })}
              onBlur={() => saveAuto({ interval_minutes: auto.interval_minutes })}
              style={{ width: 90 }}
            />
          </Space>
          <Button icon={<ThunderboltOutlined />} loading={sending} onClick={runNow}>
            Şimdi Çalıştır
          </Button>
          <span style={{ color: "#6b7689", fontSize: 12 }}>
            Yalnızca hazır (doğrulanmış, gönderilmemiş) gün/vardiyalar gönderilir — idempotent.
          </span>
        </Space>
      </Card>

      <Card title="Gün × Vardiya Matrisi" style={{ marginBottom: 16 }}>
        <Table
          rowKey="date"
          size="small"
          loading={loading}
          dataSource={rows}
          columns={matrixCols}
          scroll={{ x: 760 }}
          pagination={false}
        />
      </Card>

      <Card title="Gönderim Geçmişi">
        <Table
          rowKey="id"
          size="small"
          dataSource={history}
          columns={historyCols}
          locale={{ emptyText: "Henüz gönderim yapılmadı." }}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        open={preview.open}
        title={
          preview.cell
            ? `Gönderim Önizleme — ${preview.cell.production_date} · Vardiya ${preview.cell.shift}`
            : "Önizleme"
        }
        onCancel={() => setPreview({ open: false, cell: null, data: null })}
        footer={
          <Space>
            <Button onClick={() => setPreview({ open: false, cell: null, data: null })}>Kapat</Button>
            <Button
              type="primary"
              icon={<SendOutlined />}
              disabled={!preview.data?.payload}
              onClick={async () => {
                await doSubmit(preview.cell);
                setPreview({ open: false, cell: null, data: null });
              }}
            >
              Gönder
            </Button>
          </Space>
        }
      >
        {preview.data ? (
          preview.data.payload ? (
            <>
              <Text type="secondary">
                {preview.data.record_count} temiz kayıt → POST /api/v1/submit
              </Text>
              <pre
                style={{
                  background: "#0f1420",
                  border: "1px solid #252b3b",
                  borderRadius: 8,
                  padding: 14,
                  marginTop: 10,
                  fontSize: 13,
                }}
              >
                {JSON.stringify(preview.data.payload, null, 2)}
              </pre>
            </>
          ) : (
            <Text type="warning">{preview.data.skip_reason}</Text>
          )
        ) : (
          "Yükleniyor…"
        )}
      </Modal>
    </>
  );
}
