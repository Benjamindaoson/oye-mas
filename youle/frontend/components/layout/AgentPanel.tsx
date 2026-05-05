'use client';

// 400px 执行流右栏(对齐 frontend_001 agent-panel 的视觉)
// V1 行为:Auto 模式自动展开,Plan/Ask 默认折叠(实际折叠由 AppShell 控制是否渲染)
// 数据:同时合并 task store 实时步骤 与 mock 演示分组(后端缺失时退化)
import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, X } from 'lucide-react';
import clsx from 'clsx';
import { useTaskStore } from '@/stores/task';
import { ROLES, type RoleKey } from '@/lib/agents';
import { MOCK_EXEC_GROUPS, type ExecGroup, type ExecStep } from '@/lib/mock-data';

export function AgentPanel() {
  const liveSteps = useTaskStore((s) => s.currentSteps);

  const liveGroups = useMemo<ExecGroup[]>(() => {
    if (!liveSteps.length) return [];
    const byAgent = new Map<string, ExecGroup>();
    for (const ls of liveSteps) {
      const role = (ls.agent_id as RoleKey) || 'agent_1';
      const key = role;
      let g = byAgent.get(key);
      if (!g) {
        g = {
          id: `live-${role}`,
          agent: role as ExecGroup['agent'],
          title: `${ROLES[role]?.name ?? role} 进行中`,
          time_label: '实时',
          steps: [],
        };
        byAgent.set(key, g);
      }
      const status: ExecStep['status'] =
        ls.status === 'completed' ? 'done' : ls.status === 'pending' ? 'pending' : 'running';
      g.steps.push({
        id: ls.step_id,
        label: ls.step_id,
        status,
        detail: ls.streaming_chunks?.slice(-60),
      });
    }
    return Array.from(byAgent.values());
  }, [liveSteps]);

  const groups = liveGroups.length ? liveGroups : MOCK_EXEC_GROUPS;
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  return (
    <section className="flex h-screen flex-col overflow-hidden border-l border-wechat-line bg-white">
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-wechat-line px-3.5">
        <div>
          <div className="text-[13px] font-semibold text-wechat-fg">执行流</div>
          <div className="mt-px text-[11px] text-wechat-sub">
            已工作 4&apos;38&quot; · {groups.length} 个分组
          </div>
        </div>
        <button type="button" className="toolbar-btn" title="折叠右栏">
          <X size={14} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {groups.map((g, i) => {
          const meta = ROLES[g.agent];
          const isCollapsed = collapsed[g.id];
          const running = g.steps.some((s) => s.status === 'running');
          return (
            <div key={g.id}>
              {i > 0 && (
                <div className="my-3 flex items-center gap-2 text-[10px] text-wechat-mute">
                  <span className="h-px flex-1 bg-wechat-line" />
                  <span className="whitespace-nowrap">— {g.time_label} —</span>
                  <span className="h-px flex-1 bg-wechat-line" />
                </div>
              )}
              <div className="mb-1.5 overflow-hidden rounded-lg border border-wechat-line bg-neutral-50">
                <button
                  type="button"
                  onClick={() =>
                    setCollapsed((prev) => ({ ...prev, [g.id]: !prev[g.id] }))
                  }
                  className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-neutral-100"
                >
                  <span
                    className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
                    style={{ background: meta.color }}
                  >
                    {meta.initial}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12px] font-semibold text-wechat-fg">
                      {g.title}
                    </div>
                    <div className="mt-px text-[10px] text-wechat-sub">{g.time_label}</div>
                  </div>
                  {running && <span className="pill flex-shrink-0">进行中</span>}
                  <ChevronDown
                    size={12}
                    className={clsx(
                      'flex-shrink-0 text-wechat-mute transition-transform',
                      isCollapsed && '-rotate-90',
                    )}
                  />
                </button>
                {!isCollapsed && (
                  <ol className="border-t border-neutral-100 px-3 py-1.5">
                    {g.steps.map((s, idx) => (
                      <StepRow
                        key={s.id}
                        step={s}
                        agentColor={meta.color}
                        isLast={idx === g.steps.length - 1}
                      />
                    ))}
                  </ol>
                )}
              </div>
            </div>
          );
        })}
        {groups.length === 0 && (
          <div className="grid h-full place-items-center text-[12px] text-wechat-mute">
            等待任务派发……
          </div>
        )}
      </div>
    </section>
  );
}

function StepRow({
  step,
  agentColor,
  isLast,
}: {
  step: ExecStep;
  agentColor: string;
  isLast: boolean;
}) {
  const cursorVisible = useBlinkingCursor();
  return (
    <li className="flex items-start gap-0">
      <div className="flex w-[22px] flex-shrink-0 flex-col items-center pt-2">
        {step.status === 'done' && (
          <span className="z-10 grid h-3.5 w-3.5 place-items-center rounded-full bg-wechat-green text-white">
            <Check size={8} strokeWidth={3.5} />
          </span>
        )}
        {step.status === 'running' && (
          <span
            className="z-10 h-3.5 w-3.5 animate-spin rounded-full border-[2.5px] border-t-transparent"
            style={{ borderColor: agentColor, borderTopColor: 'transparent' }}
          />
        )}
        {step.status === 'pending' && (
          <span className="z-10 h-3.5 w-3.5 rounded-full border border-neutral-200 bg-neutral-50" />
        )}
        {!isLast && (
          <span
            className="mt-0.5 min-h-[18px] flex-1"
            style={{
              width: 1.5,
              background: step.status === 'done' ? '#07c160' : '#e5e5e5',
            }}
          />
        )}
      </div>
      <div className={clsx('min-w-0 flex-1 pl-2 pt-1.5', isLast ? 'pb-1' : 'pb-2.5')}>
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={clsx(
              'text-[12px]',
              step.status === 'pending'
                ? 'text-wechat-mute'
                : step.status === 'running'
                  ? 'font-semibold text-wechat-fg'
                  : 'text-wechat-fg',
            )}
          >
            {step.label}
          </span>
          {step.status !== 'pending' && step.word_count && (
            <span className="pill">{step.word_count}</span>
          )}
        </div>
        {step.status === 'running' && (
          <>
            {step.progress !== undefined && (
              <div className="mt-1 h-[3px] overflow-hidden rounded bg-wechat-green-soft">
                <span
                  className="block h-full bg-wechat-green transition-all"
                  style={{ width: `${step.progress}%` }}
                />
              </div>
            )}
            {step.detail && (
              <div className="mt-1 flex items-center gap-px text-[11px] text-neutral-600">
                <span>{step.detail}</span>
                <span
                  className={clsx(
                    'inline-block h-[11px] w-[1.5px] rounded-sm bg-wechat-fg transition-opacity',
                    cursorVisible ? 'opacity-100' : 'opacity-0',
                  )}
                />
              </div>
            )}
          </>
        )}
        {step.status === 'done' && step.detail && !step.word_count && (
          <div className="mt-px text-[11px] text-wechat-sub">{step.detail}</div>
        )}
      </div>
    </li>
  );
}

function useBlinkingCursor() {
  const [v, setV] = useState(true);
  useEffect(() => {
    const t = setInterval(() => setV((x) => !x), 530);
    return () => clearInterval(t);
  }, []);
  return v;
}
