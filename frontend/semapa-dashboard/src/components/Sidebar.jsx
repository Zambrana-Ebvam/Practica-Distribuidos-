import { menuItems } from "../data/menuItems";
import "../styles/app_layout.css";

function Sidebar({
  activeTab,
  onChangeTab,
  visibleTabs = [],
  usuario,
  onLogout,
}) {
  function abrirTotem() {
    window.open("/totem", "_blank", "width=1100,height=760");
  }

  const itemsVisibles = menuItems.filter((item) =>
    visibleTabs.includes(item.id)
  );

  return (
    <aside className="lay-sidebar">
      <div className="lay-brand">
        <div className="lay-logo">S</div>

        <div>
          <h2>SEMAPA</h2>
          <p>Big Data Cassandra</p>
        </div>
      </div>

      {usuario && (
        <div className="lay-user-box">
          <strong>{usuario.nombre}</strong>
          <span>Rol: {usuario.rol}</span>
        </div>
      )}

      <nav className="lay-nav">
        {itemsVisibles.map((item) => (
          <button
            key={item.id}
            className={activeTab === item.id ? "active" : ""}
            onClick={() => onChangeTab(item.id)}
          >
            {item.label}
          </button>
        ))}

        <button onClick={abrirTotem}>Tótem</button>
      </nav>

      {usuario && (
        <button className="lay-logout-button" onClick={onLogout}>
          Cerrar sesión
        </button>
      )}
    </aside>
  );
}

export default Sidebar;