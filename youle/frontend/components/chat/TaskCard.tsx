'use client';

// Agent 产出的"任务卡片"消息(对齐 frontend_001 视觉)
import { ArrowRight, FileText, Image as ImageIcon, PenLine, Video } from 'lucide-react';
import type { AgentCardMessage } from '@/stores/conversation';

const ICONS = {
  doc: FileText,
  pen: PenLine,
  image: ImageIcon,
  video: Video,
};

export function TaskCard({
  card,
  agentColor,
}: {
  card: AgentCardMessage['card'];
  agentColor: string;
}) {
  const Icon = ICONS[card.icon];
  const isDone = card.tag_status === 'done';

  return (
    <div className="w-[480px] max-w-full overflow-hidden rounded-md border border-wechat-line bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-neutral-100 px-3.5 py-2.5">
        <span
          className="grid h-[18px] w-[18px] flex-shrink-0 place-items-center rounded-sm text-white"
          style={{ background: agentColor }}
        >
          <Icon size={10} strokeWidth={2.5} />
        </span>
        <span className="flex-1 truncate text-[12px] font-semibold text-wechat-fg">
          {card.title}
        </span>
        <span className="flex-shrink-0 text-[10px] font-medium text-wechat-green">
          {card.tag}
        </span>
      </div>

      {!isDone && card.progress !== undefined && (
        <div className="h-[3px] bg-neutral-100">
          <span
            className="block h-full bg-wechat-green transition-all"
            style={{ width: `${card.progress}%` }}
          />
        </div>
      )}

      <div className="px-3.5 py-2.5">
        {card.word_count && (
          <div className="mb-2">
            <span className="pill">{card.word_count}</span>
          </div>
        )}

        <ul className="flex flex-col gap-1">
          {card.items.map((it, i) => (
            <li
              key={i}
              className="flex items-start gap-1.5 text-[12px] leading-[1.6] text-neutral-700"
            >
              <span className="flex-shrink-0 font-bold leading-[1.6] text-wechat-green">·</span>
              <span>{it}</span>
            </li>
          ))}
        </ul>

        {card.footer && (
          <button
            type="button"
            className="mt-2 flex items-center gap-1 border-t border-neutral-100 pt-2 text-[11px] text-[#5B9DD9]"
          >
            <ArrowRight size={10} strokeWidth={2.5} />
            {card.footer}
          </button>
        )}
      </div>
    </div>
  );
}
