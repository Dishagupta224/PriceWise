import { Activity, Bell, Boxes, LayoutDashboard, PanelRightOpen, Percent } from "lucide-react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/products", label: "Products", icon: Boxes },
  { to: "/decisions", label: "Decisions", icon: Activity },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/insights/margin", label: "Margin Insights", icon: Percent },
];

function SidebarNav() {
  return (
    <aside className="border-b border-line/70 bg-slate-950/[0.35] px-3 py-3 backdrop-blur lg:min-h-screen lg:border-b-0 lg:border-r lg:px-6 lg:py-6">
      <div className="panel-soft mb-4 flex items-center gap-3 px-3 py-3 lg:mb-6 lg:px-4 lg:py-4">
        <div className="rounded-2xl bg-accent/[0.15] p-3 text-accent">
          <PanelRightOpen size={20} />
        </div>
        <div className="min-w-0">
          <p className="label">Command Center</p>
          <h1 className="truncate text-base font-semibold text-slate-50 lg:text-lg">SmartPriceAgent</h1>
        </div>
      </div>

      <nav className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              [
                "flex min-w-fit items-center gap-2 rounded-2xl border px-3 py-2.5 text-sm transition lg:gap-3 lg:px-4 lg:py-3",
                isActive
                  ? "border-accent/40 bg-accent/[0.12] text-slate-50"
                  : "border-transparent bg-slate-900/25 text-muted hover:border-line/80 hover:text-slate-100",
              ].join(" ")
            }
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export default SidebarNav;
