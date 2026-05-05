"use client"

import { useState } from "react"

const AGENTS = {
  user:     { name: "老板",  color: "#e8755a", initial: "老" },
  analyst:  { name: "研究员", color: "#7eb872", initial: "研" },
  writer:   { name: "文案师", color: "#e8a47e", initial: "文" },
}

type AgentKey = keyof typeof AGENTS

interface Message {
  id: string
  agent: AgentKey
  time?: string
  type: "text" | "card" | "user"
  text?: string
  card?: {
    icon: "doc" | "pen"
    title: string
    tag: string
    tagStatus: "done" | "running"
    items: string[]
    footer?: string
    wordCount?: string
    progress?: number
  }
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: "1", agent: "user", type: "user",
    text: "@研究员 做反诈视频，2026 案例",
  },
  {
    id: "2", agent: "analyst", time: "14:36", type: "text",
    text: "明白，先确认两点：受众？案例侧重？",
  },
  {
    id: "3", agent: "user", type: "user",
    text: "城市老人 + 投资理财",
  },
  {
    id: "4", agent: "analyst", time: "14:38", type: "card",
    card: {
      icon: "doc",
      title: "研究交付",
      tag: "研究报告 · md",
      tagStatus: "done",
      items: [
        "8 个高质量案例",
        "上海老人虚拟币案例，损失 80 万——核心案例",
        "杭州高息理财 App，涉案 2.3 亿——第二案例",
        "4 个共性特征：AI 投顾包装 / 小额引诱 / 老带新 / 锁仓",
      ],
      footer: "在右栏查看执行细节",
      wordCount: "2,140 字",
    },
  },
  {
    id: "5", agent: "writer", time: "14:38", type: "text",
    text: "扫了简报，开始写脚本",
  },
  {
    id: "6", agent: "writer", time: "14:40", type: "card",
    card: {
      icon: "pen",
      title: "小文写作中",
      tag: "反诈脚本_v1 · 2/4 段 · 进行中",
      tagStatus: "running",
      items: [
        '第 1 段：引入 / "老张今年 68 岁，退休工程师，独居……"',
        "第 2 段：事件，收益数字漂漂亮亮地涨着，半年里被投入 80 万……",
      ],
      wordCount: "156 / 380 字",
      progress: 41,
    },
  },
]

export default function ChatWindow({
  chatName,
}: {
  chatName: string
}) {
  const [message, setMessage] = useState("")
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES)
  const [showScreenshotMenu, setShowScreenshotMenu] = useState(false)

  function handleSend() {
    if (!message.trim()) return
    const newMsg: Message = {
      id: Date.now().toString(),
      agent: "user",
      type: "user",
      text: message.trim(),
    }
    setMessages(prev => [...prev, newMsg])
    setMessage("")
  }

  return (
    <div style={{
      flex: 1, minWidth: 0, height: "100vh",
      display: "flex", flexDirection: "column",
      background: "#f5f5f5",
    }}>
      {/* 顶部标题栏 */}
      <div style={{
        height: 56, flexShrink: 0,
        background: "#fff",
        borderBottom: "1px solid #e5e5e5",
        display: "flex", alignItems: "center",
        justifyContent: "space-between",
        padding: "0 16px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#191919" }}>{chatName}</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#bbb" strokeWidth="2.2" style={{ cursor: "pointer" }}>
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
          {[
            <svg key="a" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#bbb" strokeWidth="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>,
            <svg key="b" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#bbb" strokeWidth="1.8"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.62 3.38 2 2 0 0 1 3.6 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" /></svg>,
            <svg key="c" width="18" height="18" viewBox="0 0 24 24" fill="#bbb"><circle cx="5" cy="12" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="19" cy="12" r="1.5" /></svg>,
          ].map((icon, i) => (
            <div key={i} style={{
              width: 30, height: 30, borderRadius: 4, cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
              onMouseEnter={e => (e.currentTarget.style.background = "#f0f0f0")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >{icon}</div>
          ))}
        </div>
      </div>

      {/* 消息区 */}
      <div style={{
        flex: 1, overflowY: "auto",
        padding: "16px 32px",
        display: "flex", flexDirection: "column", gap: 0,
      }}>
        {/* 时间戳 */}
        <div style={{ textAlign: "center", marginBottom: 16 }}>
          <span style={{
            fontSize: 11, color: "#999",
            background: "rgba(0,0,0,0.05)",
            padding: "2px 10px", borderRadius: 3,
          }}>14:35</span>
        </div>

        {messages.map(msg => {
          const agent = AGENTS[msg.agent]
          const isUser = msg.agent === "user"
          return (
            <div key={msg.id} style={{
              display: "flex",
              flexDirection: isUser ? "row-reverse" : "row",
              alignItems: "flex-start",
              gap: 10, marginBottom: 14,
            }}>
              {/* 头像 */}
              <div style={{
                width: 36, height: 36, borderRadius: 4, flexShrink: 0,
                background: agent.color,
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "#fff",
                fontSize: agent.initial === "HR" ? 9 : 12,
                fontWeight: 700,
              }}>
                {agent.initial}
              </div>

              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: isUser ? "flex-end" : "flex-start",
                maxWidth: "72%",
              }}>
                {/* 角色徽章 + 时间 */}
                {!isUser && (
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                    <span style={{
                      fontSize: 11, fontWeight: 600, color: "#07c160",
                      background: "#e8f6ee", borderRadius: 3, padding: "2px 7px",
                    }}>{agent.name}</span>
                    {msg.time && <span style={{ fontSize: 11, color: "#bbb" }}>{msg.time}</span>}
                  </div>
                )}

                {/* 文字气泡 */}
                {(msg.type === "text" || msg.type === "user") && (
                  <div style={{ position: "relative" }}>
                    {isUser ? (
                      <div style={{
                        position: "absolute", right: -6, top: 10, width: 0, height: 0,
                        borderTop: "6px solid transparent", borderBottom: "6px solid transparent",
                        borderLeft: "6px solid #95ec69",
                      }} />
                    ) : (
                      <div style={{
                        position: "absolute", left: -6, top: 10, width: 0, height: 0,
                        borderTop: "6px solid transparent", borderBottom: "6px solid transparent",
                        borderRight: "6px solid #fff",
                      }} />
                    )}
                    <div style={{
                      background: isUser ? "#95ec69" : "#fff",
                      borderRadius: 6, padding: "8px 12px",
                      fontSize: 13, color: "#191919", lineHeight: 1.65,
                      boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
                    }}>
                      {msg.text?.split(/(@\S+)/g).map((part, i) =>
                        part.startsWith("@")
                          ? <span key={i} style={{ color: "#5b9dd9", fontWeight: 600 }}>{part}</span>
                          : <span key={i}>{part}</span>
                      )}
                    </div>
                  </div>
                )}

                {/* 任务卡片 */}
                {msg.type === "card" && msg.card && (
                  <TaskCard card={msg.card} agentColor={agent.color} />
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* 底部输入区 */}
      <div style={{
        flexShrink: 0, background: "#fff",
        borderTop: "1px solid #e5e5e5",
      }}>
        <div style={{ padding: "10px 16px 6px" }}>
          <textarea
            value={message}
            onChange={e => setMessage(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() } }}
            placeholder="@一下 AI 员工，分配任务..."
            style={{
              width: "100%", minHeight: 68, resize: "none",
              border: "none", outline: "none", background: "transparent",
              fontSize: 13, color: "#191919", lineHeight: 1.65,
              fontFamily: "inherit", caretColor: "#07c160",
            }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", paddingBottom: 6 }}>
            <button onClick={handleSend} style={{
              padding: "4px 16px", borderRadius: 3, fontSize: 12,
              border: "1px solid #e5e5e5",
              background: message.trim() ? "#07c160" : "#f5f5f5",
              color: message.trim() ? "#fff" : "#bbb",
              cursor: message.trim() ? "pointer" : "default",
              fontFamily: "inherit",
            }}>发送</button>
          </div>
        </div>

        {/* 工具栏 */}
        <div style={{
          borderTop: "1px solid #e5e5e5",
          padding: "4px 14px 8px",
          display: "flex", alignItems: "center", gap: 2,
        }}>
          <ToolBtn title="发送文件">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="1.8">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          </ToolBtn>
          <div style={{ display: "flex", alignItems: "center", position: "relative" }}>
            <ToolBtn title="截图">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="1.8">
                <circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" />
                <line x1="20" y1="4" x2="8.12" y2="15.88" />
                <line x1="14.47" y1="14.48" x2="20" y2="20" />
                <line x1="8.12" y1="8.12" x2="12" y2="12" />
              </svg>
            </ToolBtn>
            <div
              onClick={() => setShowScreenshotMenu(v => !v)}
              style={{
                height: 30, display: "flex", alignItems: "center",
                justifyContent: "center", cursor: "pointer",
                paddingRight: 2, marginLeft: -4, borderRadius: "0 3px 3px 0",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "#f0f0f0")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <svg width="9" height="9" viewBox="0 0 24 24" fill="#bbb"><path d="M7 10l5 5 5-5z" /></svg>
            </div>
            {showScreenshotMenu && (
              <>
                <div style={{ position: "fixed", inset: 0, zIndex: 99 }} onClick={() => setShowScreenshotMenu(false)} />
                <div style={{
                  position: "absolute", bottom: 38, left: 0, zIndex: 100,
                  background: "#fff", border: "1px solid #e5e5e5",
                  borderRadius: 4, boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
                  minWidth: 120, overflow: "hidden",
                }}>
                  {["隐藏窗口截图", "设置"].map(label => (
                    <div key={label} onClick={() => setShowScreenshotMenu(false)}
                      style={{ padding: "7px 14px", fontSize: 12, color: "#191919", cursor: "pointer" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "#f5f5f5")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >{label}</div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function TaskCard({
  card, agentColor,
}: {
  card: NonNullable<Message["card"]>
  agentColor: string
}) {
  const isDone = card.tagStatus === "done"
  return (
    <div style={{
      background: "#fff",
      borderRadius: 6,
      border: `1px solid ${isDone ? "#e5e5e5" : "#e5e5e5"}`,
      width: 480,
      maxWidth: "100%",
      boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      overflow: "hidden",
    }}>
      {/* 卡片头 */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "10px 14px 9px",
        borderBottom: "1px solid #f0f0f0",
      }}>
        <div style={{
          width: 18, height: 18, borderRadius: 3,
          background: agentColor,
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          {card.icon === "doc" ? (
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
              <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          )}
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#191919", flex: 1 }}>{card.title}</span>
        <span style={{
          fontSize: 10, color: "#07c160",
          fontWeight: 500, flexShrink: 0,
        }}>{card.tag}</span>
      </div>

      {/* 进度条（仅 running） */}
      {card.tagStatus === "running" && card.progress !== undefined && (
        <div style={{ height: 3, background: "#f0f0f0" }}>
          <div style={{
            height: "100%", width: `${card.progress}%`,
            background: "#07c160", transition: "width 0.3s",
          }} />
        </div>
      )}

      {/* 内容 */}
      <div style={{ padding: "10px 14px" }}>
        {/* 字数标签 */}
        {card.wordCount && (
          <div style={{ marginBottom: 8 }}>
            <span style={{
              fontSize: 10, color: "#07c160",
              background: "#e8f6ee", borderRadius: 3, padding: "2px 7px",
            }}>{card.wordCount}</span>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {card.items.map((item, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "flex-start", gap: 6,
              fontSize: 12, color: "#333", lineHeight: 1.6,
            }}>
              <span style={{ color: "#07c160", fontWeight: 700, flexShrink: 0, lineHeight: 1.6 }}>·</span>
              <span>{item}</span>
            </div>
          ))}
        </div>

        {card.footer && (
          <div style={{
            marginTop: 8, paddingTop: 8,
            borderTop: "1px solid #f0f0f0",
            fontSize: 11, color: "#5b9dd9", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 4,
          }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#5b9dd9" strokeWidth="2.5">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
            {card.footer}
          </div>
        )}
      </div>
    </div>
  )
}

function ToolBtn({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <div title={title} style={{
      width: 30, height: 30, borderRadius: 3,
      display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer",
    }}
      onMouseEnter={e => (e.currentTarget.style.background = "#f0f0f0")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
    >{children}</div>
  )
}
