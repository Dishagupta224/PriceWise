import { Wifi, WifiOff } from "lucide-react";
import { useLiveFeed } from "../../context/LiveFeedContext";

function HeaderBar() {
  const { isConnected } = useLiveFeed();

  return (
    <header className="sticky top-0 z-10 border-b border-line/70 bg-ink/80 backdrop-blur">
      <div className="flex items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div>
          <p className="label">Pricing Operations</p>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-50">SmartPriceAgent</h2>
        </div>

        <div
          className={[
            "status-pill",
            isConnected
              ? "border-success/40 bg-success/10 text-success"
              : "border-danger/40 bg-danger/10 text-danger",
          ].join(" ")}
        >
          <span
            className={[
              "inline-block h-2.5 w-2.5 rounded-full",
              isConnected ? "bg-success" : "bg-danger",
            ].join(" ")}
          />
          {isConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
          <span>{isConnected ? "Live feed connected" : "WebSocket disconnected"}</span>
        </div>
      </div>
    </header>
  );
}

export default HeaderBar;
