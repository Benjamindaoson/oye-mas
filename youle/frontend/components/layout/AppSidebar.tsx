'use client';

// 60px 应用栏 — 顶部用户头像 + 4 个 nav(聊天 / 知识库 / 成果库 / 设置)
// ADR-016 简化:取消通讯录等多余入口
import { useState } from 'react';
import { BookOpen, MessageSquare, Package, Settings } from 'lucide-react';
import clsx from 'clsx';

type NavId = 'chat' | 'materials' | 'results' | 'settings';

const ITEMS: { id: NavId; label: string; icon: typeof MessageSquare; badge?: number }[] = [
  { id: 'chat',      label: '聊天',   icon: MessageSquare, badge: 57 },
  { id: 'materials', label: '知识库', icon: BookOpen },
  { id: 'results',   label: '成果库', icon: Package },
];

export function AppSidebar() {
  const [active, setActive] = useState<NavId>('chat');

  return (
    <nav className="flex h-screen w-[60px] flex-shrink-0 flex-col items-center border-r border-wechat-line bg-neutral-50 py-3">
      <button
        type="button"
        className="mb-4 h-[34px] w-[34px] overflow-hidden rounded-full"
        title="个人资料"
      >
        <span className="grid h-full w-full place-items-center bg-wechat-green-soft text-[12px] font-semibold text-wechat-green">
          老板
        </span>
      </button>

      {ITEMS.map((it) => (
        <NavBtn
          key={it.id}
          active={active === it.id}
          onClick={() => setActive(it.id)}
          label={it.label}
          badge={it.badge}
        >
          <it.icon size={20} strokeWidth={1.8} />
        </NavBtn>
      ))}

      <div className="flex-1" />

      <NavBtn
        active={active === 'settings'}
        onClick={() => setActive('settings')}
        label="设置"
      >
        <Settings size={20} strokeWidth={1.8} />
      </NavBtn>
    </nav>
  );
}

function NavBtn({
  active,
  onClick,
  label,
  badge,
  children,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  badge?: number;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={clsx(
        'relative mb-2 flex h-9 w-9 items-center justify-center rounded transition-colors',
        active
          ? 'border border-wechat-green bg-wechat-green-soft text-wechat-green'
          : 'border border-transparent text-neutral-500 hover:bg-neutral-200/60',
      )}
    >
      {children}
      {badge !== undefined && (
        <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold leading-none text-white">
          {badge}
        </span>
      )}
    </button>
  );
}
