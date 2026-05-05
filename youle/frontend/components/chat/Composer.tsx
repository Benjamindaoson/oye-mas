'use client';

// 微信式输入区:textarea + 工具栏(发送文件 / 截图 / 表情 / 发送按钮)
// 严肃场景(conversation.serious_mode)关闭表情入口
import { useState } from 'react';
import {
  ChevronDown,
  Folder,
  Scissors,
  Smile,
} from 'lucide-react';
import clsx from 'clsx';
import { useConversationStore } from '@/stores/conversation';
import { useSendMessage } from '@/lib/api';
import { EmojiPicker } from '@/components/chat/EmojiPicker';

export function Composer({ conversationId }: { conversationId: string }) {
  const [text, setText] = useState('');
  const [showEmoji, setShowEmoji] = useState(false);
  const conv = useConversationStore((s) => s.list.find((c) => c.id === conversationId));
  const appendMessage = useConversationStore((s) => s.appendMessage);
  const send = useSendMessage(conversationId);

  function dispatch() {
    const trimmed = text.trim();
    if (!trimmed) return;
    appendMessage({
      id: `local-${Date.now()}`,
      conversation_id: conversationId,
      kind: 'user_text',
      role: 'user',
      text: trimmed,
    });
    send.mutate(trimmed);
    setText('');
  }

  const seriousMode = conv?.serious_mode;
  const canSend = text.trim().length > 0;

  return (
    <div className="relative flex-shrink-0 border-t border-wechat-line bg-white">
      <div className="px-4 pb-1.5 pt-2.5">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              dispatch();
            }
          }}
          placeholder="@一下 AI 员工,分配任务..."
          className="w-full min-h-[68px] resize-none border-none bg-transparent text-[13px] leading-[1.65] text-wechat-fg outline-none caret-wechat-green placeholder:text-wechat-mute"
        />
        <div className="flex justify-end pb-1.5">
          <button
            type="button"
            onClick={dispatch}
            disabled={!canSend}
            className={clsx(
              'rounded-sm border border-wechat-line px-4 py-1 text-[12px] transition-colors',
              canSend
                ? 'bg-wechat-green text-white hover:bg-[#06AE56]'
                : 'cursor-not-allowed bg-neutral-100 text-wechat-mute',
            )}
          >
            发送
          </button>
        </div>
      </div>

      <div className="flex items-center gap-0.5 border-t border-wechat-line px-3.5 py-1.5">
        <button type="button" className="toolbar-btn" title="发送文件">
          <Folder size={18} strokeWidth={1.8} />
        </button>
        <button type="button" className="toolbar-btn" title="截图">
          <Scissors size={18} strokeWidth={1.8} />
        </button>
        <button
          type="button"
          className="toolbar-btn"
          title="截图选项"
          onClick={() => undefined}
        >
          <ChevronDown size={9} className="text-wechat-mute" />
        </button>
        {!seriousMode && (
          <button
            type="button"
            className="toolbar-btn"
            title="表情"
            onClick={() => setShowEmoji((v) => !v)}
          >
            <Smile size={18} strokeWidth={1.8} />
          </button>
        )}
      </div>

      {showEmoji && !seriousMode && (
        <EmojiPicker
          onClose={() => setShowEmoji(false)}
          onPick={(emoji) => {
            setText((t) => t + emoji);
            setShowEmoji(false);
          }}
        />
      )}
    </div>
  );
}
