"use client"

import { useState, useEffect } from "react"

type StepStatus = "done" | "running" | "pending"

interface Step {
  id: string
  label: string
  status: StepStatus
  detail?: string
  wordCount?: string
  progress?: number
}

interface AgentTask {
  id: string
  agentName: string
  agentColor: string
  agentInitial: string
  taskTitle: string
  timeLabel: string
  steps: Step[]
  collapsed: boolean
}

const TASKS: AgentTask[] = [
  {
    id: "1",
    agentName: "小研",
    agentColor: "#7eb872",
    agentInitial: "研",
    taskTitle: "调研反诈视频 2026 案例",
    timeLabel: "调研 4'12\"",
    collapsed: false,
    steps: [
      { id: "s1", label: "阅读素材", status: "done", detail: "读取 3 个参考文档" },
      { id: "s2", label: "搜索案例", status: "done", detail: "找到 8 个真实案例" },
      { id: "s3", label: "整理特征", status: "done", detail: "4 个共性特征 · 2 个新型手法" },
      { id: "s4", label: "输出报告", status: "done", detail: "2,140 字", wordCount: "2,140 字" },
    ],
  },
  {
    id: "2",
    agentName: "小文",
    agentColor: "#e8a47e",
    agentInitial: "文",
    taskTitle: "小文写作中 · 写第 2 段",
    timeLabel: "写作 4'38\"",
    collapsed: false,
    steps: [
      { id: "s1", label: "引入", status: "done", detail: "32 字", wordCount: "32 字" },
      { id: "s2", label: "第 2 段", status: "running", detail: "收益数字漂漂亮亮地涨着，半年里被", wordCount: "156 / 380 字", progress: 41 },
      { id: "s3", label: "第 3 段", status: "pending" },
      { id: "s4", label: "收尾", status: "pending" },
    ],
  },
  {
    id: "3",
    agentName: "小文",
    agentColor: "#e8a47e",
    agentInitial: "文",
    taskTitle: "小文写作中",
    timeLabel: "写作 4'38\"",
    collapsed: false,
    steps: [
      { id: "s1", label: "完成 第 1 段：引入", status: "done", detail: "32 字", wordCount: "32 字" },
      { id: "s2", label: "写作 第 2 段", status: "running", detail: "156 / 380 字", wordCount: "156 / 380 字", progress: 41 },
      { id: "s3", label: "第 3 段", status: "pending" },
      { id: "s4", label: "收尾", status: "pending" },
    ],
  },
]

export default function AgentPanel({ onClose }: { onClose?: () => void }) {
  const [tasks, setTasks] = useState<AgentTask[]>(TASKS)
  const [cursorVisible, setCursorVisible] = useState(true)

  useEffect(() => {
    const t = setInterval(() => setCursorVisible(v => !v), 530)
    return () => clearInterval(t)
  }, [])

  function toggleCollapse(id: string) {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, collapsed: !t.collapsed } : t))
  }

  return (
    <div style={{
      width: "100%", height: "100vh", flexShrink: 0,
      display: "flex", flexDirection: "column",
      background: "#fff",
      borderLeft: "1px solid #e5e5e5",
      overflow: "hidden",
    }}>
      {/* 顶部标题栏 */}
      <div style={{
        height: 56, flexShrink: 0,
        borderBottom: "1px solid #e5e5e5",
        display: "flex", alignItems: "center",
        justifyContent: "space-between",
        padding: "0 14px",
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#191919" }}>执行流</div>
          <div style={{ fontSize: 11, color: "#999", marginTop: 1 }}>
            已工作 4&apos;38&apos;&apos; · 5 个 Agent
          </div>
        </div>
        <div
          onClick={onClose}
          style={{
            width: 26, height: 26, borderRadius: 4, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = "#f0f0f0")}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2.2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </div>
      </div>

      {/* 任务内容 */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 12px" }}>
        {tasks.map((task, taskIdx) => (
          <div key={task.id}>
            {/* 分组间的时间分割线 */}
            {taskIdx > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "12px 0" }}>
                <div style={{ flex: 1, height: 1, background: "#e5e5e5" }} />
                <span style={{ fontSize: 10, color: "#bbb", whiteSpace: "nowrap" }}>
                  — 写作 · {task.timeLabel} —
                </span>
                <div style={{ flex: 1, height: 1, background: "#e5e5e5" }} />
              </div>
            )}

            {/* 任务分组卡片 */}
            <div style={{
              background: "#fafafa",
              borderRadius: 8,
              border: "1px solid #e5e5e5",
              overflow: "hidden",
              marginBottom: 6,
            }}>
              {/* 卡片头 */}
              <div
                onClick={() => toggleCollapse(task.id)}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "9px 12px 8px", cursor: "pointer",
                }}
                onMouseEnter={e => (e.currentTarget.style.background = "#f3f3f3")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                {/* 实心彩色圆形头像 */}
                <div style={{
                  width: 24, height: 24, borderRadius: "50%",
                  background: task.agentColor, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#fff", fontSize: 10, fontWeight: 700,
                }}>
                  {task.agentInitial}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 12, fontWeight: 600, color: "#191919",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>{task.taskTitle}</div>
                  <div style={{ fontSize: 10, color: "#999", marginTop: 1 }}>{task.timeLabel}</div>
                </div>
                {/* 进行中标签 */}
                {task.steps.some(s => s.status === "running") && (
                  <span style={{
                    fontSize: 10, color: "#07c160",
                    background: "#e8f6ee", borderRadius: 3, padding: "2px 6px",
                    fontWeight: 500, flexShrink: 0,
                  }}>进行中</span>
                )}
                <svg
                  width="12" height="12" viewBox="0 0 24 24" fill="#bbb"
                  style={{ transform: task.collapsed ? "rotate(-90deg)" : "none", transition: "transform 0.2s", flexShrink: 0 }}
                >
                  <path d="M7 10l5 5 5-5z" />
                </svg>
              </div>

              {/* 步骤列表 */}
              {!task.collapsed && (
                <div style={{ padding: "6px 12px 10px", borderTop: "1px solid #f0f0f0" }}>
                  {task.steps.map((step, idx) => (
                    <div key={step.id} style={{
                      display: "flex", alignItems: "flex-start", gap: 0,
                    }}>
                      {/* 时间轴节点 + 竖线 */}
                      <div style={{
                        display: "flex", flexDirection: "column", alignItems: "center",
                        width: 22, flexShrink: 0, paddingTop: 9,
                      }}>
                        {step.status === "done" && (
                          <div style={{
                            width: 14, height: 14, borderRadius: "50%",
                            background: "#07c160", flexShrink: 0, zIndex: 1,
                            display: "flex", alignItems: "center", justifyContent: "center",
                          }}>
                            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          </div>
                        )}
                        {step.status === "running" && (
                          <div style={{
                            width: 14, height: 14, borderRadius: "50%",
                            border: `2.5px solid ${task.agentColor}`,
                            borderTopColor: "transparent",
                            flexShrink: 0, zIndex: 1,
                            animation: "spin 0.8s linear infinite",
                          }} />
                        )}
                        {step.status === "pending" && (
                          <div style={{
                            width: 14, height: 14, borderRadius: "50%",
                            border: "1.5px solid #e0e0e0",
                            background: "#f9f9f9", flexShrink: 0, zIndex: 1,
                          }} />
                        )}
                        {idx < task.steps.length - 1 && (
                          <div style={{
                            width: 1.5, flex: 1, minHeight: 18, marginTop: 2,
                            background: step.status === "done" ? "#07c160" : "#e5e5e5",
                          }} />
                        )}
                      </div>

                      {/* 步骤内容 */}
                      <div style={{
                        flex: 1, minWidth: 0,
                        paddingTop: 6, paddingLeft: 8,
                        paddingBottom: idx < task.steps.length - 1 ? 10 : 4,
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          <span style={{
                            fontSize: 12,
                            color: step.status === "pending" ? "#bbb" : "#191919",
                            fontWeight: step.status === "running" ? 600 : 400,
                          }}>{step.label}</span>
                          {step.status !== "pending" && step.wordCount && (
                            <span style={{
                              fontSize: 10,
                              color: step.status === "running" ? "#07c160" : "#07c160",
                              background: "#e8f6ee",
                              borderRadius: 3, padding: "1px 5px", flexShrink: 0,
                            }}>{step.wordCount}</span>
                          )}
                        </div>

                        {/* 进行中：进度条 + 打字游标 */}
                        {step.status === "running" && (
                          <>
                            {step.progress !== undefined && (
                              <div style={{ marginTop: 4, height: 3, background: "#e8f6ee", borderRadius: 2, overflow: "hidden" }}>
                                <div style={{
                                  height: "100%", width: `${step.progress}%`,
                                  background: "#07c160", transition: "width 0.3s",
                                }} />
                              </div>
                            )}
                            {step.detail && (
                              <div style={{
                                fontSize: 11, color: "#666", marginTop: 3,
                                display: "flex", alignItems: "center", gap: 1,
                              }}>
                                <span>{step.detail}</span>
                                <span style={{
                                  display: "inline-block", width: 1.5, height: 11,
                                  background: "#191919",
                                  opacity: cursorVisible ? 1 : 0,
                                  borderRadius: 1, transition: "opacity 0.1s",
                                }} />
                              </div>
                            )}
                          </>
                        )}

                        {step.status === "done" && step.detail && !step.wordCount && (
                          <div style={{ fontSize: 11, color: "#999", marginTop: 1 }}>{step.detail}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
