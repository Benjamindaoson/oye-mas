'use client';

// REST 客户端骨架。前端铁律:fetch().then(res => res.json) → 必须 TanStack Query。
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { useUserStore } from '@/stores/user';
import {
  MOCK_CONVERSATIONS,
  MOCK_MEMBERS,
  MOCK_MESSAGES,
} from '@/lib/mock-data';
import type {
  AgentMember,
  ConversationSummary,
  Message,
  WorkMode,
} from '@/stores/conversation';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== 'false';

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = useUserStore.getState().token;
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

async function safeRequest<T>(path: string, fallback: T, init?: RequestInit): Promise<T> {
  if (USE_MOCK) return fallback;
  try {
    return await request<T>(path, init);
  } catch {
    return fallback;
  }
}

export function useConversations(opts?: Partial<UseQueryOptions<ConversationSummary[]>>) {
  return useQuery<ConversationSummary[]>({
    queryKey: ['conversations'],
    queryFn: () => safeRequest('/api/conversations', MOCK_CONVERSATIONS),
    ...opts,
  });
}

export function useMembers(
  conversationId: string | null,
  opts?: Partial<UseQueryOptions<AgentMember[]>>,
) {
  return useQuery<AgentMember[]>({
    queryKey: ['members', conversationId],
    enabled: !!conversationId,
    queryFn: () =>
      safeRequest(
        `/api/conversations/${conversationId}/members`,
        MOCK_MEMBERS[conversationId ?? ''] ?? [],
      ),
    ...opts,
  });
}

export function useMessages(
  conversationId: string | null,
  opts?: Partial<UseQueryOptions<Message[]>>,
) {
  return useQuery<Message[]>({
    queryKey: ['messages', conversationId],
    enabled: !!conversationId,
    queryFn: () =>
      safeRequest(
        `/api/conversations/${conversationId}/messages`,
        MOCK_MESSAGES[conversationId ?? ''] ?? [],
      ),
    ...opts,
  });
}

export function useSendMessage(conversationId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) => {
      if (USE_MOCK || !conversationId) {
        return { id: `local-${Date.now()}`, text };
      }
      return request(`/api/conversations/${conversationId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content: text }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['messages', conversationId] });
    },
  });
}

export function useSwitchWorkMode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { conversationId: string; target: WorkMode }) => {
      if (USE_MOCK) return { ok: true, ...vars };
      return request(`/api/conversations/${vars.conversationId}/switch-work-mode`, {
        method: 'POST',
        body: JSON.stringify({ target: vars.target, triggered_by: 'user' }),
      });
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['conversations'] });
      void vars;
    },
  });
}

export function useHitlDecision(taskId: string, gateId: string) {
  return useMutation({
    mutationFn: async (vars: {
      action: 'approve' | 'modify';
      payload?: Record<string, unknown>;
    }) => {
      if (USE_MOCK) return { ok: true, ...vars };
      return request(`/api/tasks/${taskId}/hitl_gates/${gateId}/${vars.action}`, {
        method: 'POST',
        body: JSON.stringify(vars.payload ?? {}),
      });
    },
  });
}
