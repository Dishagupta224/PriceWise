import { useEffect, useMemo, useRef, useState } from "react";
import { Wifi, WifiOff } from "lucide-react";
import { useLiveFeed } from "../../context/LiveFeedContext";
import { getRuntimeSessionStatus, startRuntimeSession } from "../../services/api";

function formatCountdown(secondsTotal) {
  const safe = Math.max(0, secondsTotal);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function HeaderBar() {
  const { isConnected } = useLiveFeed();
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [nowMs, setNowMs] = useState(Date.now());
  const wasActiveRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function bootstrapSession() {
      try {
        const session = await startRuntimeSession();
        if (!cancelled) {
          setRuntimeStatus(session);
          setStatusMessage("");
          wasActiveRef.current = Boolean(session.active);
        }
      } catch (error) {
        if (!cancelled) {
          setStatusMessage(error?.response?.data?.detail || "Runtime activation failed.");
        }
      }
    }

    async function refreshStatus() {
      try {
        const status = await getRuntimeSessionStatus();
        if (!cancelled) {
          if (status.active) {
            setStatusMessage("");
          } else if (wasActiveRef.current && !status.active) {
            setStatusMessage("Your 8-minute AI usage window has ended.");
          } else if (!status.active && Number(status.activations_remaining_today) === 0) {
            setStatusMessage("Daily AI usage limit reached. Try again tomorrow.");
          }
          wasActiveRef.current = Boolean(status.active);
          setRuntimeStatus(status);
        }
      } catch (error) {
        if (!cancelled) {
          setStatusMessage(error?.response?.data?.detail || "Could not refresh runtime status.");
        }
      }
    }

    bootstrapSession();
    const statusInterval = window.setInterval(refreshStatus, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(statusInterval);
    };
  }, []);

  useEffect(() => {
    const tick = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, []);

  const runtimeSecondsRemaining = useMemo(() => {
    if (!runtimeStatus?.active || !runtimeStatus?.expires_at) {
      return 0;
    }
    const expiresMs = Date.parse(runtimeStatus.expires_at);
    if (Number.isNaN(expiresMs)) {
      return 0;
    }
    return Math.max(0, Math.ceil((expiresMs - nowMs) / 1000));
  }, [runtimeStatus, nowMs]);

  const runtimeBadgeClass = runtimeStatus?.active
    ? "border-accent/40 bg-accent/10 text-accent"
    : "border-warning/40 bg-warning/10 text-warning";

  useEffect(() => {
    if (!runtimeStatus?.active || runtimeSecondsRemaining > 0) {
      return;
    }
    setRuntimeStatus((current) =>
      current
        ? {
            ...current,
            active: false,
            expires_at: null,
          }
        : current,
    );
    if (!statusMessage) {
      setStatusMessage("Your 8-minute AI usage window has ended.");
    }
  }, [runtimeStatus, runtimeSecondsRemaining, statusMessage]);

  useEffect(() => {
    if (runtimeStatus?.active && statusMessage) {
      setStatusMessage("");
    }
  }, [runtimeStatus?.active, statusMessage]);

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
      <div className="flex flex-wrap items-center gap-2 px-4 pb-3 sm:px-6 lg:px-8">
        <div className={["status-pill", runtimeBadgeClass].join(" ")}>
          <span>
            {runtimeStatus?.active
              ? `Runtime active ${formatCountdown(runtimeSecondsRemaining)}`
              : "Runtime inactive"}
          </span>
        </div>
        <div className="status-pill border-line/70 bg-slate-900/40 text-muted">
          <span>
            Global uses today: {runtimeStatus?.activations_used_today ?? 0}/{runtimeStatus?.activations_limit_per_day ?? 15}
          </span>
        </div>
        {statusMessage ? <p className="text-xs text-warning">{statusMessage}</p> : null}
      </div>
    </header>
  );
}

export default HeaderBar;
