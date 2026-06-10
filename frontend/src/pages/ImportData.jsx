import { useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  Col,
  Popconfirm,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Upload,
} from "antd";
import {
  CloseOutlined,
  DeleteOutlined,
  InboxOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";

const { Dragger } = Upload;

const PREVIEW_ROWS = 10;
const PREVIEW_BYTES = 64 * 1024; // only the head of the file is read for preview

// Minimal CSV line splitter for the preview (handles quoted fields).
const splitCsvLine = (line) => {
  const out = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out;
};

// Read the first rows of the file client-side, before any upload happens.
// UTF-8 is tried first; mojibake (�) falls back to Windows-1254 (the MES export encoding).
const readPreview = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Dosya okunamadı."));
    reader.onload = () => {
      const truncated = file.size > PREVIEW_BYTES;
      const decode = (enc) => {
        let lines = new TextDecoder(enc).decode(reader.result).split(/\r?\n/);
        if (truncated) lines = lines.slice(0, -1); // drop the cut-off last line
        return lines.filter((l) => l.trim() !== "");
      };
      let lines = decode("utf-8");
      if (lines.some((l) => l.includes("�"))) lines = decode("windows-1254");
      if (lines.length === 0) return reject(new Error("Dosya boş görünüyor."));
      resolve({
        header: splitCsvLine(lines[0]),
        rows: lines.slice(1, 1 + PREVIEW_ROWS).map(splitCsvLine),
        truncated,
      });
    };
    reader.readAsArrayBuffer(file.slice(0, PREVIEW_BYTES));
  });

export default function ImportData() {
  const { message, modal } = App.useApp();
  const [uploading, setUploading] = useState(false);
  const [percent, setPercent] = useState(0);
  const [processing, setProcessing] = useState(null); // {phase, processed, total}
  const [result, setResult] = useState(null);
  const [batches, setBatches] = useState([]);
  const [preview, setPreview] = useState(null); // {file, header, rows, truncated}

  const loadBatches = () => api.listBatches().then((r) => setBatches(r.data));
  useEffect(() => {
    loadBatches();
  }, []);

  // Poll batch status until import + validation finish (work runs in background).
  const pollBatch = (id) => {
    const tick = async () => {
      try {
        const { data } = await api.getBatch(id);
        setProcessing({ phase: data.phase, processed: data.processed_rows, total: data.total_rows });
        if (data.status === "completed") {
          setResult(data);
          setUploading(false);
          setProcessing(null);
          message.success(`${data.total_rows} kayıt içe aktarıldı ve doğrulandı.`);
          loadBatches();
          return;
        }
        if (data.status === "failed") {
          setUploading(false);
          setProcessing(null);
          message.error(`İçe aktarma başarısız: ${data.error_message || "bilinmeyen hata"}`);
          loadBatches();
          return;
        }
        setTimeout(tick, 1000);
      } catch (err) {
        setUploading(false);
        setProcessing(null);
        message.error(err.userMessage);
      }
    };
    tick();
  };

  // §5.1: show the first rows and wait for explicit confirmation before uploading.
  const handleSelect = async (file) => {
    try {
      const p = await readPreview(file);
      setPreview({ file, ...p });
      setResult(null);
    } catch (err) {
      message.error(err.message);
    }
    return false; // never let antd auto-upload
  };

  const doUpload = async (file) => {
    setPreview(null);
    setUploading(true);
    setPercent(0);
    setResult(null);
    setProcessing(null);
    try {
      const res = await api.uploadCsv(file, (e) => {
        if (e.total) setPercent(Math.round((e.loaded / e.total) * 100));
      });
      // Backend returns immediately with a 'processing' batch; poll for progress.
      pollBatch(res.data.id);
    } catch (err) {
      setUploading(false);
      if (err.response?.status === 409) {
        modal.warning({
          title: "Yinelenen dosya",
          content: `Bu dosya daha önce yüklendi (batch #${err.response.data.detail.batch_id}).`,
        });
      } else {
        message.error(err.userMessage);
      }
    }
    return false; // prevent antd's default upload
  };

  const handleDelete = async (batch) => {
    try {
      await api.deleteBatch(batch.id);
      message.success(`"${batch.filename}" ve kayıtları silindi.`);
      if (result?.id === batch.id) setResult(null);
      loadBatches();
    } catch (err) {
      message.error(err.userMessage);
    }
  };

  const processPercent =
    processing && processing.total ? Math.round((processing.processed / processing.total) * 100) : 0;

  const columns = [
    { title: "#", dataIndex: "id", width: 60 },
    { title: "Dosya", dataIndex: "filename", ellipsis: true },
    { title: "Toplam", dataIndex: "total_rows" },
    { title: "Temiz", dataIndex: "clean_rows", render: (v) => <span style={{ color: "#22c55e" }}>{v}</span> },
    { title: "Uyarı", dataIndex: "warning_rows", render: (v) => <span style={{ color: "#f59e0b" }}>{v}</span> },
    { title: "Hata", dataIndex: "error_rows", render: (v) => <span style={{ color: "#ef4444" }}>{v}</span> },
    {
      title: "Tarih",
      dataIndex: "created_at",
      render: (v) => dayjs(v).format("DD.MM.YYYY HH:mm"),
    },
    {
      title: "",
      key: "actions",
      width: 60,
      render: (_, row) => (
        <Popconfirm
          title="Yüklemeyi sil"
          description={`"${row.filename}" ile gelen tüm kayıtlar ve validasyon sonuçları silinecek.`}
          okText="Sil"
          okButtonProps={{ danger: true }}
          cancelText="Vazgeç"
          onConfirm={() => handleDelete(row)}
        >
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            disabled={row.status === "processing"}
          />
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Veri Yükle"
        subtitle="MES CSV dosyasını yükleyin — sistem otomatik olarak validasyon çalıştırır"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={result ? 14 : 24}>
          <Card>
            <Dragger
              accept=".csv"
              multiple={false}
              showUploadList={false}
              beforeUpload={handleSelect}
              disabled={uploading}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">CSV dosyasını buraya sürükleyin veya tıklayın</p>
              <p className="ant-upload-hint">
                Yüklemeden önce ilk {PREVIEW_ROWS} satır önizlenir. Windows-1254 / UTF-8
                desteklenir. Aynı dosya tekrar yüklenirse uyarılırsınız.
              </p>
            </Dragger>
            {preview && !uploading && (
              <Card
                size="small"
                title={`Önizleme — ${preview.file.name} (ilk ${preview.rows.length} satır)`}
                style={{ marginTop: 16 }}
                extra={
                  <Space>
                    <Button icon={<CloseOutlined />} onClick={() => setPreview(null)}>
                      Vazgeç
                    </Button>
                    <Button
                      type="primary"
                      icon={<UploadOutlined />}
                      onClick={() => doUpload(preview.file)}
                    >
                      Yükle ve Doğrula
                    </Button>
                  </Space>
                }
              >
                <Table
                  size="small"
                  rowKey="__k"
                  scroll={{ x: "max-content" }}
                  pagination={false}
                  columns={preview.header.map((h, i) => ({
                    title: h || `Kolon ${i + 1}`,
                    dataIndex: String(i),
                    ellipsis: true,
                  }))}
                  dataSource={preview.rows.map((r, k) => ({
                    __k: k,
                    ...Object.fromEntries(r.map((v, i) => [String(i), v])),
                  }))}
                />
                <div style={{ color: "#8694a8", fontSize: 13, marginTop: 8 }}>
                  {preview.header.length} kolon algılandı.
                  {preview.truncated && " Önizleme dosyanın başından okunur; tamamı yüklemede işlenir."}
                </div>
              </Card>
            )}
            {uploading && (
              <div style={{ marginTop: 16 }}>
                {!processing ? (
                  <>
                    <Progress percent={percent} status="active" />
                    <div style={{ color: "#8694a8", fontSize: 13 }}>Dosya yükleniyor…</div>
                  </>
                ) : (
                  <>
                    <Progress
                      percent={processing.phase === "validating" ? 100 : processPercent}
                      status="active"
                    />
                    <div style={{ color: "#8694a8", fontSize: 13 }}>
                      {processing.phase === "validating"
                        ? "Doğrulanıyor… (kalite kontrolleri çalışıyor)"
                        : `İçe aktarılıyor… ${processing.processed.toLocaleString("tr-TR")} / ${processing.total.toLocaleString("tr-TR")}`}
                    </div>
                  </>
                )}
              </div>
            )}
          </Card>
        </Col>

        {result && (
          <Col xs={24} lg={10}>
            <Card title={`İçe Aktarma Özeti — batch #${result.id}`}>
              <Row gutter={[12, 12]}>
                <Col span={12}>
                  <Statistic title="Toplam Satır" value={result.total_rows} />
                </Col>
                <Col span={12}>
                  <Statistic title="Temiz" value={result.clean_rows} valueStyle={{ color: "#22c55e" }} />
                </Col>
                <Col span={12}>
                  <Statistic title="Uyarı" value={result.warning_rows} valueStyle={{ color: "#f59e0b" }} />
                </Col>
                <Col span={12}>
                  <Statistic title="Hata" value={result.error_rows} valueStyle={{ color: "#ef4444" }} />
                </Col>
              </Row>
              <Button type="link" href="/validation" style={{ paddingLeft: 0, marginTop: 8 }}>
                Validasyon raporunu görüntüle →
              </Button>
            </Card>
          </Col>
        )}
      </Row>

      <Card title="İçe Aktarma Geçmişi" style={{ marginTop: 16 }}>
        <Table
          rowKey="id"
          size="small"
          dataSource={batches}
          columns={columns}
          pagination={false}
        />
      </Card>
    </>
  );
}
