'use client';

// 240px 会话列表 — 搜索 + 列表 + 折叠置顶
// 数据来自 useConversations(mock fallback);点选后 setCurrent + 路由跳转
import { useRouter } from 'next/navigation';
import { ChevronUp, Plus, Search } from 'lucide-react';
import clsx from 'clsx';
import { useState } from 'react';
import { useConversationStore, type ConversationSummary } from '@/stores/conversation';

export function ChatList() {
  const list = useConversationStore((s) => s.list);
  const currentId = useConversationStore((s) => s.currentId);
  const setCurrent = useConversationStore((s) => s.setCurrent);
  const router = useRouter();
  const [keyword, setKeyword] = useState('');

  const filtered = keyword
    ? list.filter((c) => c.name.includes(keyword) || c.preview?.includes(keyword))
    : list;

  function pick(c: ConversationSummary) {
    setCurrent(c.id);
    if (c.kind === 'main_session') router.push('/');
    else router.push(`/chat/${c.id}`);
  }

  return (
    <aside className="flex h-screen w-[240px] flex-shrink-0 flex-col border-r border-wechat-line bg-white">
      <div className="px-3 py-2">
        <label className="flex h-7 items-center gap-2 rounded bg-neutral-100 px-2">
          <Search size={12} strokeWidth={2.2} className="text-neutral-400" />
          <input
            type="text"
            placeholder="搜索"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            className="flex-1 bg-transparent text-[12px] text-wechat-fg outline-none placeholder:text-wechat-mute"
          />
          <button
            type="button"
            title="发起新会话"
            className="grid h-4 w-4 place-items-center rounded text-neutral-400 hover:text-wechat-green"
          >
            <Plus size={12} strokeWidth={2} />
          </button>
        </label>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="px-4 py-8 text-center text-[12px] text-wechat-mute">
            还没有会话,去主会话开始吧
          </div>
        )}
        {filtered.map((c) => (
          <ChatRow key={c.id} chat={c} active={currentId === c.id} onClick={() => pick(c)} />
        ))}
      </div>

      <div className="flex flex-shrink-0 cursor-pointer items-center gap-1.5 border-t border-wechat-line px-3.5 py-2 text-[12px] text-wechat-sub hover:bg-neutral-100">
        <span className="text-neutral-400">≡</span>
        <span className="flex-1">折叠置顶聊天</span>
        <ChevronUp size={11} className="text-wechat-mute" />
      </div>
    </aside>
  );
}

function ChatRow({
  chat,
  active,
  onClick,
}: {
  chat: ConversationSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'flex h-14 w-full items-center gap-2.5 rounded-md px-2 transition-colors',
        active ? 'bg-wechat-green-soft' : 'hover:bg-neutral-100',
      )}
      style={{ margin: '0 4px', width: 'calc(100% - 8px)' }}
    >
      <ChatAvatar chat={chat} />
      <div className="min-w-0 flex-1 text-left">
        <div className="mb-0.5 flex items-baseline justify-between">
          <span className="truncate text-[13px] font-medium text-wechat-fg">{chat.name}</span>
          {chat.preview_time && (
            <span className="ml-1 flex-shrink-0 text-[11px] text-wechat-mute">
              {chat.preview_time}
            </span>
          )}
        </div>
        <div className="truncate text-[11px] text-wechat-sub">{chat.preview ?? ''}</div>
      </div>
    </button>
  );
}

function ChatAvatar({ chat }: { chat: ConversationSummary }) {
  const SIZE = 'h-9 w-9 flex-shrink-0';
  if (chat.avatar_image) {
    /* eslint-disable-next-line @next/next/no-img-element */
    return <img src={chat.avatar_image} alt={chat.name} className={`${SIZE} rounded object-cover`} />;
  }
  if (chat.avatar_colors) {
    return (
      <div className={`${SIZE} grid grid-cols-2 gap-[1.5px] overflow-hidden rounded`}>
        {chat.avatar_colors.map((c, i) => (
          <span key={i} style={{ background: c }} />
        ))}
      </div>
    );
  }
  return (
    <div
      className={`${SIZE} flex items-center justify-center rounded text-[12px] font-semibold text-white`}
      style={{ background: chat.avatar_bg ?? '#999' }}
    >
      {chat.avatar_text ?? chat.name.slice(0, 1)}
    </div>
  );
}
