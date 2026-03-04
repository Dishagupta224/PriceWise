import { createContext, useContext } from "react";
import useWebSocket from "../hooks/useWebSocket";

const LiveFeedContext = createContext(null);

function buildWebSocketUrl() {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.hostname || "localhost";
  return `${protocol}://${host}:8000/ws/live-feed`;
}

export function LiveFeedProvider({ children }) {
  const websocket = useWebSocket(buildWebSocketUrl());
  return <LiveFeedContext.Provider value={websocket}>{children}</LiveFeedContext.Provider>;
}

export function useLiveFeed() {
  const context = useContext(LiveFeedContext);
  if (!context) {
    throw new Error("useLiveFeed must be used inside LiveFeedProvider.");
  }
  return context;
}
