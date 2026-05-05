"use client"

const CHATS = [
  {
    id: "1",
    name: "特别助理",
    sub: "今天有什么需要我帮忙？",
    time: "06:08",
    avatarType: "single" as const,
    avatarBg: "#f4c95d",
    avatarText: "助",
  },
  {
    id: "2",
    name: "HR经理",
    sub: "上次任务已完成",
    time: "昨天",
    avatarType: "single" as const,
    avatarBg: "#5b9dd9",
    avatarText: "HR",
  },
  {
    id: "3",
    name: "你的第1个专属AI团队",
    sub: "@一下，你就有了",
    time: "05:49",
    avatarType: "image" as const,
    avatarBg: "",
    avatarText: "",
    avatarImage: "/team-avatar.png",
  },
  {
    id: "4",
    name: "反诈视频制作群",
    sub: "大壮: 这个模板不错",
    time: "04:11",
    avatarType: "grid" as const,
    avatarBg: "",
    avatarText: "",
    avatarColors: ["#e05a5a", "#f4c95d", "#7eb872", "#5b9dd9"],
  },
  {
    id: "5",
    name: "电商作图群",
    sub: "晓琳: 新素材发群里了",
    time: "昨天",
    avatarType: "grid" as const,
    avatarBg: "",
    avatarText: "",
    avatarColors: ["#e8a47e", "#f4c95d", "#a07bc8", "#bbb"],
  },
]

type Chat = typeof CHATS[number]

export default function ChatList({
  selectedId,
  onSelect,
}: {
  selectedId: string
  onSelect: (id: string) => void
}) {
  return (
    <div style={{
      width: 240,
      flexShrink: 0,
      height: "100vh",
      background: "#fff",
      borderRight: "1px solid #e5e5e5",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
    }}>
      {/* 搜索框 */}
      <div style={{ padding: "10px 12px 8px", flexShrink: 0 }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          background: "#f5f5f5",
          borderRadius: 4,
          padding: "0 8px",
          height: 28,
          gap: 6,
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#bbb" strokeWidth="2.2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            placeholder="搜索"
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontSize: 12,
              color: "#191919",
              fontFamily: "inherit",
            }}
          />
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#bbb" strokeWidth="2" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </div>
      </div>

      {/* 列表 */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {CHATS.map(chat => (
          <ChatRow
            key={chat.id}
            chat={chat}
            active={selectedId === chat.id}
            onClick={() => onSelect(chat.id)}
          />
        ))}
      </div>

      {/* 底部 */}
      <div style={{
        borderTop: "1px solid #e5e5e5",
        padding: "8px 14px",
        display: "flex",
        alignItems: "center",
        gap: 6,
        cursor: "pointer",
        flexShrink: 0,
      }}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="1.8">
          <line x1="3" y1="7" x2="21" y2="7" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="17" x2="21" y2="17" />
        </svg>
        <span style={{ fontSize: 12, color: "#999", flex: 1 }}>折叠置顶聊天</span>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#bbb" strokeWidth="2.2">
          <polyline points="18 15 12 9 6 15" />
        </svg>
      </div>
    </div>
  )
}

function ChatRow({ chat, active, onClick }: { chat: Chat; active: boolean; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        height: 56,
        padding: "0 8px",
        margin: "0 4px",
        borderRadius: 6,
        background: active ? "#e8f6ee" : "transparent",
        cursor: "pointer",
        transition: "background 0.1s",
      }}
      onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "#f7f7f7" }}
      onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent" }}
    >
      <ChatAvatar chat={chat} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 2 }}>
          <span style={{
            fontSize: 13, color: "#191919", fontWeight: 500,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            maxWidth: 118,
          }}>
            {chat.name}
          </span>
          <span style={{ fontSize: 11, color: "#bbb", flexShrink: 0, marginLeft: 4 }}>
            {chat.time}
          </span>
        </div>
        <div style={{
          fontSize: 11, color: "#999",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {chat.sub}
        </div>
      </div>
    </div>
  )
}

function ChatAvatar({ chat }: { chat: Chat }) {
  const S = 36
  if (chat.avatarType === "image") {
    return (
      <img src={chat.avatarImage} alt={chat.name}
        style={{ width: S, height: S, borderRadius: 4, objectFit: "cover", flexShrink: 0 }} />
    )
  }
  if (chat.avatarType === "grid") {
    return (
      <div style={{
        width: S, height: S, borderRadius: 4,
        display: "grid", gridTemplateColumns: "1fr 1fr",
        gap: 1.5, overflow: "hidden", flexShrink: 0,
      }}>
        {chat.avatarColors!.map((c, i) => (
          <div key={i} style={{ background: c }} />
        ))}
      </div>
    )
  }
  return (
    <div style={{
      width: S, height: S, borderRadius: 4,
      background: chat.avatarBg,
      display: "flex", alignItems: "center", justifyContent: "center",
      color: "#fff", fontSize: 12, fontWeight: 600, flexShrink: 0,
    }}>
      {chat.avatarText}
    </div>
  )
}
