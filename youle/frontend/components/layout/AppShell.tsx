'use client';

// 四栏布局壳:60px AppSidebar / 240px ChatList / 1fr 中栏 / 400px AgentPanel
// 中栏由 children 决定(主会话首次入群 onboarding / 群聊 / 空态)
// AgentPanel 仅在选中"群"且非 plan/ask 折叠时展示
import { useEffect } from 'react';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { ChatList } from '@/components/layout/ChatList';
import { AgentPanel } from '@/components/layout/AgentPanel';
import { useConversationStore } from '@/stores/conversation';
import { useConversations } from '@/lib/api';
import { useUserStore } from '@/stores/user';
import { useWsLifecycle } from '@/lib/ws';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: conversations } = useConversations();
  const setList = useConversationStore((s) => s.setList);
  const list = useConversationStore((s) => s.list);
  const currentId = useConversationStore((s) => s.currentId);
  const setCurrent = useConversationStore((s) => s.setCurrent);
  const token = useUserStore((s) => s.token);

  useWsLifecycle(token);

  useEffect(() => {
    if (conversations && conversations.length) setList(conversations);
  }, [conversations, setList]);

  useEffect(() => {
    if (!currentId && list.length) {
      const main = list.find((c) => c.kind === 'main_session') ?? list[0];
      if (main) setCurrent(main.id);
    }
  }, [list, currentId, setCurrent]);

  const current = list.find((c) => c.id === currentId) ?? null;
  const showAgentPanel =
    !!current && current.kind !== 'private_chat' && current.work_mode === 'auto';

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-wechat-bg">
      <AppSidebar />
      <ChatList />
      <main className="flex min-w-0 flex-1 overflow-hidden">{children}</main>
      {showAgentPanel && (
        <aside className="w-[400px] flex-shrink-0">
          <AgentPanel />
        </aside>
      )}
    </div>
  );
}
