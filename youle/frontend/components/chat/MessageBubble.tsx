'use client';

// 单条消息渲染:气泡 / 卡片 / 互动 / HITL
// 严肃场景由 conversation.serious_mode 控制(铁律 §19:严肃场景关闭表情)
import clsx from 'clsx';
import type {
  AgentCardMessage,
  HitlImageMessage,
  HitlScriptMessage,
  HitlVideoMessage,
  Message,
} from '@/stores/conversation';
import { ROLES } from '@/lib/agents';
import { TaskCard } from '@/components/chat/TaskCard';
import { ScriptApproval } from '@/components/hitl/ScriptApproval';
import { ImageSelection } from '@/components/hitl/ImageSelection';
import { VideoFinalReview } from '@/components/hitl/VideoFinalReview';
import { highlightMentions } from '@/lib/mention';

export function MessageBubble({ message }: { message: Message }) {
  const meta = ROLES[message.role];
  const isUser = message.role === 'user';
  const isSystem = message.kind === 'system';

  if (isSystem) {
    return (
      <div className="my-3 text-center">
        <span className="rounded-sm bg-black/5 px-2.5 py-0.5 text-[11px] text-wechat-mute">
          {message.text}
        </span>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'mb-3.5 flex animate-fade-up items-start gap-2.5',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <span
        className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded text-[12px] font-bold text-white"
        style={{ background: meta.color }}
      >
        {meta.initial}
      </span>

      <div
        className={clsx(
          'flex max-w-[72%] flex-col',
          isUser ? 'items-end' : 'items-start',
        )}
      >
        {!isUser && (
          <div className="mb-1 flex items-center gap-1.5">
            <span className="role-badge">{meta.name}</span>
            {message.time && (
              <span className="text-[11px] text-wechat-mute">{message.time}</span>
            )}
          </div>
        )}

        {/* 文字气泡 */}
        {(message.kind === 'user_text' ||
          message.kind === 'agent_text' ||
          message.kind === 'interaction') &&
          message.text && (
            <BubbleText
              isUser={isUser}
              text={message.text}
              isInteraction={message.kind === 'interaction'}
            />
          )}

        {/* TaskCard */}
        {message.kind === 'agent_card' && (
          <TaskCard
            card={(message as AgentCardMessage).card}
            agentColor={meta.color}
          />
        )}

        {/* HITL gates 内嵌入消息流 */}
        {message.kind === 'hitl_script' && (
          <ScriptApproval
            taskId={(message as HitlScriptMessage).task_id}
            gateId={(message as HitlScriptMessage).gate_id}
            versions={(message as HitlScriptMessage).versions}
          />
        )}
        {message.kind === 'hitl_image' && (
          <ImageSelection
            taskId={(message as HitlImageMessage).task_id}
            gateId={(message as HitlImageMessage).gate_id}
            images={(message as HitlImageMessage).images}
          />
        )}
        {message.kind === 'hitl_video' && (
          <VideoFinalReview
            taskId={(message as HitlVideoMessage).task_id}
            gateId={(message as HitlVideoMessage).gate_id}
            videoUrl={(message as HitlVideoMessage).video_url}
          />
        )}
      </div>
    </div>
  );
}

function BubbleText({
  isUser,
  text,
  isInteraction,
}: {
  isUser: boolean;
  text: string;
  isInteraction?: boolean;
}) {
  return (
    <div className="relative">
      {isUser ? (
        <span className="absolute right-[-6px] top-2.5 h-0 w-0 border-y-[6px] border-l-[6px] border-y-transparent border-l-wechat-bubble-user" />
      ) : (
        <span className="absolute left-[-6px] top-2.5 h-0 w-0 border-y-[6px] border-r-[6px] border-y-transparent border-r-white" />
      )}
      <div
        className={clsx(
          'rounded-md px-3 py-2 text-[13px] leading-[1.65] shadow-sm',
          isUser
            ? 'bg-wechat-bubble-user text-wechat-fg'
            : 'bg-white text-wechat-fg',
          isInteraction && 'italic text-wechat-sub',
        )}
      >
        {highlightMentions(text)}
      </div>
    </div>
  );
}
