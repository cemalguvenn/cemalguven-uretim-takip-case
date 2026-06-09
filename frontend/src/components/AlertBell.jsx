import { useEffect, useState } from "react";
import { Badge, Button, Dropdown, Empty, List, Tag } from "antd";
import { BellOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";

import api from "../api/client.js";
import { SEVERITY_COLORS } from "../theme.js";

// Header bell that polls /api/alerts (failed syncs, high-error batches, anomalies).
export default function AlertBell() {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    let active = true;
    const load = () => api.alerts().then((r) => active && setAlerts(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, []);

  const panel = (
    <div
      style={{
        width: 360,
        maxHeight: 420,
        overflow: "auto",
        background: "#171c2b",
        border: "1px solid #2b3346",
        borderRadius: 10,
        padding: 8,
      }}
    >
      {alerts.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Uyarı yok" style={{ padding: 16 }} />
      ) : (
        <List
          dataSource={alerts}
          renderItem={(a) => (
            <List.Item
              style={{ cursor: a.link ? "pointer" : "default", padding: "10px 12px" }}
              onClick={() => a.link && navigate(a.link)}
            >
              <List.Item.Meta
                title={
                  <span>
                    <Tag color={SEVERITY_COLORS[a.severity]} style={{ marginRight: 8 }}>
                      {a.severity}
                    </Tag>
                    {a.title}
                  </span>
                }
                description={<span style={{ color: "#8694a8" }}>{a.detail}</span>}
              />
            </List.Item>
          )}
        />
      )}
    </div>
  );

  return (
    <Dropdown popupRender={() => panel} trigger={["click"]} placement="bottomRight">
      <Badge count={alerts.length} size="small" offset={[-2, 4]}>
        <Button type="text" icon={<BellOutlined style={{ fontSize: 18, color: "#c7cdda" }} />} />
      </Badge>
    </Dropdown>
  );
}
