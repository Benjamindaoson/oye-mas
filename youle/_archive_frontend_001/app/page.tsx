"use client"

import { useState } from "react"
import Sidebar from "@/components/wechat/sidebar"
import ChatList from "@/components/wechat/chat-list"
import ChatWindow from "@/components/wechat/chat-window"
import AgentPanel from "@/components/wechat/agent-panel"

const AI_TEAM_CHAT_ID = "3"

export default function Page() {
  const [selectedId, setSelectedId] = useState(AI_TEAM_CHAT_ID)
  const [panelOpen, setPanelOpen] = useState(true)
  const showPanel = selectedId === AI_TEAM_CHAT_ID && panelOpen

  const CHAT_NAMES: Record<string, string> = {
    "1": "特别助理",
    "2": "HR经理",
    "3": "你的第1个专属AI团队",
    "4": "反诈视频制作群",
    "5": "电商作图群",
  }

  return (
    <div style={{
      display: "flex",
      height: "100vh",
      width: "100vw",
      overflow: "hidden",
      background: "#f5f5f5",
      fontFamily: "'PingFang SC', 'Inter', -apple-system, 'Microsoft YaHei', sans-serif",
    }}>
      {/* 左侧应用栏 60px */}
      <Sidebar />

      {/* 会话列表 240px */}
      <ChatList
        selectedId={selectedId}
        onSelect={id => { setSelectedId(id); setPanelOpen(true) }}
      />

      {/* 中栏 主对话区 — 自动撑满剩余 */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", overflow: "hidden" }}>
        <ChatWindow chatName={CHAT_NAMES[selectedId] ?? "对话"} />
      </div>

      {/* 右栏 执行流 400px */}
      {showPanel && (
        <div style={{ width: 400, flexShrink: 0 }}>
          <AgentPanel onClose={() => setPanelOpen(false)} />
        </div>
      )}
    </div>
  )
}
