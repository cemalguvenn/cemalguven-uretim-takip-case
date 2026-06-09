export default function PageHeader({ title, subtitle, extra }) {
  return (
    <div className="page-header" style={{ display: "flex", alignItems: "flex-end" }}>
      <div>
        <h2>{title}</h2>
        {subtitle && <div className="sub">{subtitle}</div>}
      </div>
      {extra && <div style={{ marginLeft: "auto" }}>{extra}</div>}
    </div>
  );
}
