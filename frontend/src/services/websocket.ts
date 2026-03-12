import type { WsMessage, GenerationState, SceneProgress } from '../types';

type WsCallback = (msg: WsMessage) => void;

const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_BASE = import.meta.env.VITE_WS_URL ?? `${wsProto}//${window.location.host}/ws`;

export class StoryForgeSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<WsCallback>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private projectId: string;

  constructor(projectId: string) {
    this.projectId = projectId;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(`${WS_BASE}/${this.projectId}`);

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WsMessage;
        this.listeners.forEach((cb) => cb(msg));
      } catch {
        console.error('[WS] Failed to parse message:', event.data);
      }
    };

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = (err) => {
      console.error('[WS] Error:', err);
      this.ws?.close();
    };
  }

  subscribe(cb: WsCallback): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
    this.listeners.clear();
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Convenience hook-compatible factory
const sockets = new Map<string, StoryForgeSocket>();

export function getSocket(projectId: string): StoryForgeSocket {
  let socket = sockets.get(projectId);
  if (!socket) {
    socket = new StoryForgeSocket(projectId);
    sockets.set(projectId, socket);
  }
  return socket;
}

export function cleanupSocket(projectId: string): void {
  const socket = sockets.get(projectId);
  if (socket) {
    socket.disconnect();
    sockets.delete(projectId);
  }
}

export type { WsCallback };
