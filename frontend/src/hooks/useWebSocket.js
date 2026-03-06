import { useEffect, useRef, useState } from "react";

const MAX_MESSAGES = 50;
const MAX_BACKOFF_MS = 10000;

export default function useWebSocket(url) {
  const socketRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const manuallyClosedRef = useRef(false);
  const seenKeysRef = useRef(new Set());
  const seenOrderRef = useRef([]);
  const [messages, setMessages] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  const rememberMessageKey = (key) => {
    if (!key) {
      return true;
    }
    if (seenKeysRef.current.has(key)) {
      return false;
    }
    seenKeysRef.current.add(key);
    seenOrderRef.current.push(key);
    if (seenOrderRef.current.length > 300) {
      const oldest = seenOrderRef.current.shift();
      if (oldest) {
        seenKeysRef.current.delete(oldest);
      }
    }
    return true;
  };

  const getMessageKey = (message) => {
    if (!message || typeof message !== "object") {
      return null;
    }
    if (message.type === "CONNECTED") {
      // Keep only one recent "connected" card in the live feed.
      return "CONNECTED:live-feed";
    }
    const eventId = message?.data?.event_id;
    if (eventId) {
      return `${message.type}:${eventId}`;
    }
    const productId = message?.data?.product_id ?? "na";
    const competitor = message?.data?.competitor_name ?? "na";
    const oldPrice = message?.data?.old_price ?? "na";
    const newPrice = message?.data?.new_price ?? "na";
    const timestamp = message?.timestamp ?? "na";
    return `${message.type}:${productId}:${competitor}:${oldPrice}:${newPrice}:${timestamp}`;
  };

  useEffect(() => {
    if (!url) {
      return undefined;
    }

    manuallyClosedRef.current = false;

    const connect = () => {
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        reconnectAttemptsRef.current = 0;
        setIsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed?.type === "PING" && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "PONG" }));
            return;
          }
          if (parsed?.type === "PONG") {
            return;
          }
          if (!rememberMessageKey(getMessageKey(parsed))) {
            return;
          }
          setMessages((current) => [parsed, ...current].slice(0, MAX_MESSAGES));
        } catch {
          setMessages((current) => [{ type: "RAW", data: event.data }, ...current].slice(0, MAX_MESSAGES));
        }
      };

      socket.onclose = () => {
        setIsConnected(false);
        socketRef.current = null;

        if (manuallyClosedRef.current) {
          return;
        }

        const backoff = Math.min(1000 * 2 ** reconnectAttemptsRef.current, MAX_BACKOFF_MS);
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = window.setTimeout(connect, backoff);
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      manuallyClosedRef.current = true;
      setIsConnected(false);

      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }

      if (socketRef.current && socketRef.current.readyState <= WebSocket.OPEN) {
        socketRef.current.close();
      }
    };
  }, [url]);

  const sendMessage = (payload) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return false;
    }

    const encoded = typeof payload === "string" ? payload : JSON.stringify(payload);
    socketRef.current.send(encoded);
    return true;
  };

  return { messages, isConnected, sendMessage };
}
