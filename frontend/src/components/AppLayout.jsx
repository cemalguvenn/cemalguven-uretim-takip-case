import { useState } from "react";
import { Layout, Menu, Grid } from "antd";
import {
  DashboardOutlined,
  UploadOutlined,
  TableOutlined,
  SafetyCertificateOutlined,
  CloudUploadOutlined,
  SettingOutlined,
  FundOutlined,
} from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";

import AlertBell from "./AlertBell.jsx";

const { Sider, Header, Content } = Layout;
const { useBreakpoint } = Grid;

const ITEMS = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/import", icon: <UploadOutlined />, label: "Veri Yükle" },
  { key: "/records", icon: <TableOutlined />, label: "Kayıtlar" },
  { key: "/validation", icon: <SafetyCertificateOutlined />, label: "Validasyon" },
  { key: "/loss", icon: <FundOutlined />, label: "Kayıp Analizi" },
  { key: "/sync", icon: <CloudUploadOutlined />, label: "API Gönderim" },
  { key: "/settings", icon: <SettingOutlined />, label: "Ayarlar" },
];

const TITLES = Object.fromEntries(ITEMS.map((i) => [i.key, i.label]));

export default function AppLayout({ children }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const screens = useBreakpoint();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        breakpoint="lg"
        collapsedWidth={screens.xs ? 0 : 80}
        width={232}
        style={{ borderRight: "1px solid #1f2535" }}
      >
        <div className="app-logo">
          <span className="dot" />
          {!collapsed && <span>Üretim Takip</span>}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[pathname]}
          items={ITEMS}
          onClick={({ key }) => navigate(key)}
          style={{ background: "transparent", borderInlineEnd: "none" }}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: "transparent",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            borderBottom: "1px solid #1f2535",
          }}
        >
          <h3 style={{ margin: 0, color: "#fff" }}>
            {TITLES[pathname] || "Üretim Performans Takip"}
          </h3>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ color: "#6b7689", fontSize: 13 }}>INJECTION EXTERIORS · MES</span>
            <AlertBell />
          </div>
        </Header>
        <Content style={{ padding: 24, overflow: "auto" }}>{children}</Content>
      </Layout>
    </Layout>
  );
}
