import { Tag } from "antd";
import { STATUS_META } from "../theme.js";

export default function StatusTag({ status }) {
  const meta = STATUS_META[status] || { color: "default", label: status };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}
