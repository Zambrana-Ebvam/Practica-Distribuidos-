import "../styles/app_layout.css";

function KpiCard({ title, value, subtitle }) {
  return (
    <div className="lay-kpi-card">
      <span>{title}</span>
      <strong>{value}</strong>
      {subtitle && <small>{subtitle}</small>}
    </div>
  );
}

export default KpiCard;