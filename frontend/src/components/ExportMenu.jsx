import { Button, Dropdown } from "antd";
import { DownloadOutlined } from "@ant-design/icons";

// Dropdown export button: choose CSV or PDF. Parent supplies the handlers.
export default function ExportMenu({ onCsv, onPdf, loading }) {
  return (
    <Dropdown
      menu={{
        items: [
          { key: "csv", label: "CSV indir" },
          { key: "pdf", label: "PDF indir" },
        ],
        onClick: ({ key }) => (key === "csv" ? onCsv() : onPdf()),
      }}
    >
      <Button icon={<DownloadOutlined />} loading={loading}>
        Dışa Aktar
      </Button>
    </Dropdown>
  );
}
