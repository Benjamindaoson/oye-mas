'use client';

// 原生 WebSocket + 自动重连(铁律:不用 socket.io)
// 路由 WSEvent → conversation / task / hitl store
import { useEffect } from 'react';
import { useTaskStore } from '@/stores/task';
import { useWsStore } from '@/stores/ws';
import { useHitlStore } from '@/stores/hitl';
import { useConversationStore } from '@/stores/conversation';
import type { RoleKey, AgentStatus } from '@/lib/agents';

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== 'false';

export function connectWs(token: string | null): void {
  if (USE_MOCK) return; // mock 环境不连真 WS,避免误报
  if (socket && socket.readyState <= WebSocket.OPEN) return;
  const url = `${process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws'}${
    token ? `?token=${token}` : ''
  }`;
  socket = new WebSocket(url);
  socket.onopen = () => useWsStore.getState().setConnected(true);
  socket.onclose = () => {
    useWsStore.getState().setConnected(false);
    reconnectTimer = setTimeout(() => connectWs(token), 2000);
  };
  socket.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      route(msg);
    } catch {
      /* ignore */
    }
  };
}

export function disconnectWs(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  socket?.close();
  socket = null;
}

function route(msg: { type: string; [k: string]: unknown }): void {
  const task = useTaskStore.getState();
  const hitl = useHitlStore.getState();
  const conv = useConversationStore.getState();
  switch (msg.type) {
    case 'step_started':
      task.upsertStep({
        step_id: msg.step_id as string,
        agent_id: msg.agent_id as string,
        status: 'running',
      });
      break;
    case 'step_streaming':
      task.appendChunk(msg.step_id as string, msg.chunk as string);
      break;
    case 'step_completed':
      task.upsertStep({
        step_id: msg.step_id as string,
        agent_id: '',
        status: 'completed',
        artifact: msg.artifact as never,
      });
      break;
    case 'hitl_gate_opened':
      hitl.push(msg.gate as never);
      break;
    case 'message_added':
      conv.appendMessage(
        msg.message as Parameters<typeof conv.appendMessage>[0],
      );
      break;
    case 'agent_status_changed':
      conv.patchMemberStatus(
        msg.conversation_id as string,
        msg.agent_id as RoleKey,
        msg.status as AgentStatus,
      );
      break;
    case 'work_mode_changed':
      conv.patchMode(
        msg.conversation_id as string,
        msg.to as 'plan' | 'ask' | 'auto',
      );
      break;
    case 'pong':
      break;
    default:
      break;
  }
}

export function useWsLifecycle(token: string | null): void {
  useEffect(() => {
    connectWs(token);
    return () => disconnectWs();
  }, [token]);
}
