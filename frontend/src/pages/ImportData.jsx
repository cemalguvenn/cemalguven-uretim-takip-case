import { useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  Col,
  Progress,
  Row,
  Statistic,
  Table,
  Upload,
} from "antd";
import { InboxOutlined } from "@ant-design/icons";
import dayjs from "dayjs";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";

const { Dragger } = Upload;

export default function ImportData() {
  const { message, modal } = App.useApp();
  const [uploading, setUploading] = useState(false);
  const [percent, setPercent] = useState(0);
  const [result, setResult] = useState(null);
  const [batches, setBatches] = useState([]);

  const loadBatches = () => api.listBatches().then((r) => setBatches(r.data));
  useEffect(() => {
    loadBatches();
  }, []);

  const doUpload = async (file) => {
    setUploading(true);
    setPercent(0);
    setResult(null);
    try {
      const res = await api.uploadCsv(file, (e) => {
        if (e.total) setPercent(Math.round((e.loaded / e.total) * 90));
      });
      setPercent(100);
      setResult(res.data);
      message.success(`${res.data.total_rows} kayıt içe aktarıldı ve doğrulandı.`);
      loadBatches();
    } catch (err) {
      if (err.response?.status === 409) {
        modal.warning({
          title: "Yinelenen dosya",
          content: `Bu dosya daha önce yüklendi (batch #${err.response.data.detail.batch_id}).`,
        });
      } else {
        message.error(err.userMessage);
      }
    } finally {
      setUploading(false);
    }
    return false; // prevent antd's default upload
  };

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
              beforeUpload={doUpload}
              disabled={uploading}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">CSV dosyasını buraya sürükleyin veya tıklayın</p>
              <p className="ant-upload-hint">
                Windows-1254 / UTF-8 desteklenir. Aynı dosya tekrar yüklenirse uyarılırsınız.
              </p>
            </Dragger>
            {uploading && <Progress percent={percent} status="active" style={{ marginTop: 16 }} />}
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
