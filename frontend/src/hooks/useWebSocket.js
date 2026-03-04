import { useEffect, useRef, useState } from "react";

const MAX_MESSAGES = 50;
const MAX_BACKOFF_MS = 10000;

export default function useWebSocket(url) {
  const socketRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const manuallyClosedRef = useRef(false);
  const [messages, setMessages] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

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
