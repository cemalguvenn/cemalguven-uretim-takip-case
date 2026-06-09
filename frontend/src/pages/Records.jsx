import { useEffect, useMemo, useState } from "react";
import {
  App,
  Button,
  Card,
  Col,
  DatePicker,
  Input,
  Popconfirm,
  Row,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";

import api from "../api/client.js";
import PageHeader from "../components/PageHeader.jsx";
import StatusTag from "../components/StatusTag.jsx";
import RecordDetailModal from "../components/RecordDetailModal.jsx";
import ExportMenu from "../components/ExportMenu.jsx";
import { STATUS_META } from "../theme.js";
import { downloadCsv, downloadPdf } from "../utils/export.js";
import { oeeColor } from "../utils/format.js";

const PDF_COLUMNS = [
  { key: "record_id", label: "ID" },
  { key: "tarih", label: "Tarih" },
  { key: "vardiya", label: "V" },
  { key: "is_istasyon_adi", label: "İstasyon" },
  { key: "stok_adi", label: "Stok" },
  { key: "availability", label: "A" },
  { key: "performance", label: "P" },
  { key: "quality", label: "Q" },
  { key: "oee", label: "OEE" },
  { key: "uretilen_miktar", label: "Üretilen" },
  { key: "hatali_uretilen", label: "Hatalı" },
  { key: "status", label: "Durum" },
];

const { RangePicker } = DatePicker;

const STATIONS = ["IMM-2700-1", "IMM-2700-2", "IMM-2700-3", "IMM-4000-1", "IMM-4000-2"];
const STATUS_OPTIONS = Object.entries(STATUS_META)
  .filter(([k]) => k !== "hidden")
  .map(([k, m]) => ({ value: k, label: m.label }));

export default function Records() {
  const { message } = App.useApp();
  const [filters, setFilters] = useState({
    vardiya: [], istasyon: [], status: [], stok: "",
    oee: [0, 200], onlyProblematic: false, hideErrors: false, includeHidden: false,
    range: null,
  });
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [selected, setSelected] = useState([]);
  const [modal, setModal] = useState({ open: false, id: null });

  const queryParams = useMemo(() => {
    const f = filters;
    return {
      page, page_size: pageSize,
      vardiya: f.vardiya, istasyon: f.istasyon, status: f.status,
      stok: f.stok || undefined,
      oee_min: f.oee[0] > 0 ? f.oee[0] : undefined,
      oee_max: f.oee[1] < 200 ? f.oee[1] : undefined,
      only_problematic: f.onlyProblematic || undefined,
      hide_errors: f.hideErrors || undefined,
      include_hidden: f.includeHidden || undefined,
      tarih_start: f.range ? f.range[0].format("YYYY-MM-DD") : undefined,
      tarih_end: f.range ? f.range[1].format("YYYY-MM-DD") : undefined,
    };
  }, [filters, page, pageSize]);

  const load = () => {
    setLoading(true);
    api
      .listRecords(queryParams)
      .then((r) => setData(r.data))
      .catch((e) => message.error(e.userMessage))
      .finally(() => setLoading(false));
  };

  useEffect(load, [queryParams]); // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (patch) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    setPage(1);
  };

  const runBatch = async (action) => {
    try {
      const r = await api.batchAction(selected, action);
      message.success(`${r.data.affected} kayıt: ${action}`);
      setSelected([]);
      load();
    } catch (e) {
      message.error(e.userMessage);
    }
  };

  // Fetch every matching page (backend caps page_size at 500).
  const fetchAllMatching = async () => {
    const rows = [];
    let p = 1;
    while (true) {
      const r = await api.listRecords({ ...queryParams, page: p, page_size: 500 });
      rows.push(...r.data.items);
      if (rows.length >= r.data.total || r.data.items.length === 0) break;
      p += 1;
    }
    return rows;
  };

  const exportCsv = async () => {
    message.loading({ content: "CSV hazırlanıyor…", key: "exp" });
    const rows = await fetchAllMatching();
    downloadCsv("kayitlar.csv", rows);
    message.success({ content: `${rows.length} kayıt indirildi.`, key: "exp" });
  };

  const exportPdf = async () => {
    message.loading({ content: "PDF hazırlanıyor…", key: "exp" });
    const rows = await fetchAllMatching();
    downloadPdf("kayitlar.pdf", "Üretim Kayıtları", PDF_COLUMNS, rows);
    message.success({ content: `${rows.length} kayıt PDF olarak indirildi.`, key: "exp" });
  };

  const numCol = (key) => ({
    title: key.toUpperCase(),
    dataIndex: key,
    width: 80,
    sorter: true,
    render: (v) => (v === null ? "—" : Number(v).toLocaleString("tr-TR")),
  });

  const columns = [
    { title: "ID", dataIndex: "record_id", width: 70, fixed: "left" },
    { title: "Tarih", dataIndex: "tarih", width: 110 },
    { title: "V", dataIndex: "vardiya", width: 50 },
    { title: "İstasyon", dataIndex: "is_istasyon_adi", width: 120 },
    { title: "Stok", dataIndex: "stok_adi", ellipsis: true, width: 200 },
    numCol("availability"),
    numCol("performance"),
    numCol("quality"),
    {
      title: "OEE", dataIndex: "oee", width: 90, sorter: true,
      render: (v) =>
        v === null ? "—" : <b style={{ color: oeeColor(v) }}>{Number(v).toFixed(1)}</b>,
    },
    numCol("uretilen_miktar"),
    numCol("hatali_uretilen"),
    {
      title: "Durum", dataIndex: "status", width: 120, fixed: "right",
      render: (s, row) => (
        <Space size={4}>
          <StatusTag status={s} />
          {row.error_count > 0 && <Tag color="error">{row.error_count}</Tag>}
          {row.warning_count > 0 && <Tag color="warning">{row.warning_count}</Tag>}
        </Space>
      ),
    },
    {
      title: "", key: "act", width: 70, fixed: "right",
      render: (_, row) => (
        <Button size="small" onClick={() => setModal({ open: true, id: row.id })}>
          Detay
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Kayıtlar"
        subtitle={`${data.total.toLocaleString("tr-TR")} kayıt eşleşti`}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={load}>
              Yenile
            </Button>
            <ExportMenu onCsv={exportCsv} onPdf={exportPdf} />
          </Space>
        }
      />

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} md={8}>
            <RangePicker style={{ width: "100%" }} onChange={(r) => setF({ range: r })} />
          </Col>
          <Col xs={12} md={4}>
            <Select
              mode="multiple" allowClear placeholder="Vardiya" style={{ width: "100%" }}
              options={[1, 2, 3].map((v) => ({ value: v, label: `Vardiya ${v}` }))}
              onChange={(v) => setF({ vardiya: v })}
            />
          </Col>
          <Col xs={12} md={6}>
            <Select
              mode="multiple" allowClear placeholder="İstasyon" style={{ width: "100%" }}
              options={STATIONS.map((s) => ({ value: s, label: s }))}
              onChange={(v) => setF({ istasyon: v })}
            />
          </Col>
          <Col xs={24} md={6}>
            <Select
              mode="multiple" allowClear placeholder="Durum" style={{ width: "100%" }}
              options={STATUS_OPTIONS}
              onChange={(v) => setF({ status: v })}
            />
          </Col>
          <Col xs={24} md={8}>
            <Input.Search
              allowClear placeholder="Stok / iş emri / istasyon ara"
              onSearch={(v) => setF({ stok: v })}
            />
          </Col>
          <Col xs={24} md={8}>
            <span style={{ color: "#8694a8", fontSize: 12 }}>OEE aralığı</span>
            <Slider
              range min={0} max={200} defaultValue={[0, 200]}
              onChangeComplete={(v) => setF({ oee: v })}
            />
          </Col>
          <Col xs={24} md={8}>
            <Space size="large" wrap>
              <Space size={6}>
                <Switch onChange={(v) => setF({ onlyProblematic: v })} />
                <span style={{ fontSize: 13 }}>Sadece sorunlu</span>
              </Space>
              <Space size={6}>
                <Switch onChange={(v) => setF({ hideErrors: v })} />
                <span style={{ fontSize: 13 }}>Hataları gizle</span>
              </Space>
              <Space size={6}>
                <Switch onChange={(v) => setF({ includeHidden: v })} />
                <span style={{ fontSize: 13 }}>Gizlileri göster</span>
              </Space>
            </Space>
          </Col>
        </Row>
      </Card>

      {selected.length > 0 && (
        <Space style={{ marginBottom: 12 }}>
          <span>{selected.length} kayıt seçili:</span>
          <Popconfirm title="Seçilenleri reddet?" onConfirm={() => runBatch("reject")}>
            <Button danger size="small">Toplu Reddet</Button>
          </Popconfirm>
          <Button size="small" onClick={() => runBatch("hide")}>Toplu Gizle</Button>
        </Space>
      )}

      <Table
        rowKey="id"
        size="small"
        loading={loading}
        dataSource={data.items}
        columns={columns}
        scroll={{ x: 1400 }}
        rowSelection={{ selectedRowKeys: selected, onChange: setSelected }}
        pagination={{
          current: page, pageSize, total: data.total,
          showSizeChanger: true, pageSizeOptions: [25, 50, 100, 200],
          showTotal: (t) => `Toplam ${t.toLocaleString("tr-TR")}`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />

      <RecordDetailModal
        recordId={modal.id}
        open={modal.open}
        onClose={() => setModal({ open: false, id: null })}
        onChanged={load}
      />
    </>
  );
}
