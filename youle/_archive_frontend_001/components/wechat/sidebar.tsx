"use client"
import { useState } from "react"

type NavId = "chat" | "profile" | "academy" | "settings"

export default function Sidebar() {
  const [active, setActive] = useState<NavId>("chat")

  return (
    <div style={{
      width: 60,
      flexShrink: 0,
      height: "100vh",
      background: "#fafafa",
      borderRight: "1px solid #e5e5e5",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      paddingTop: 14,
      paddingBottom: 14,
    }}>
      {/* 用户头像 */}
      <div style={{
        width: 34,
        height: 34,
        borderRadius: "50%",
        overflow: "hidden",
        marginBottom: 18,
        flexShrink: 0,
        cursor: "pointer",
      }}>
        <img
          src="/avatar.jpg"
          alt="用户头像"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>

      <NavBtn active={active === "chat"} onClick={() => setActive("chat")} label="聊天" badge={57}>
        <IconChat active={active === "chat"} />
      </NavBtn>

      <NavBtn active={active === "profile"} onClick={() => setActive("profile")} label="AI员工">
        <IconProfile active={active === "profile"} />
      </NavBtn>

      <NavBtn active={active === "academy"} onClick={() => setActive("academy")} label="AI学院">
        <IconAcademy active={active === "academy"} />
      </NavBtn>

      <div style={{ flex: 1 }} />

      <NavBtn active={active === "settings"} onClick={() => setActive("settings")} label="设置">
        <IconSettings active={active === "settings"} />
      </NavBtn>
    </div>
  )
}

function NavBtn({
  active, onClick, label, badge, children,
}: {
  active: boolean
  onClick: () => void
  label: string
  badge?: number
  children: React.ReactNode
}) {
  return (
    <div
      title={label}
      onClick={onClick}
      style={{
        position: "relative",
        width: 36,
        height: 36,
        borderRadius: 4,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: active ? "#e8f6ee" : "transparent",
        border: active ? "1px solid #07c160" : "1px solid transparent",
        cursor: "pointer",
        marginBottom: 6,
        transition: "background 0.12s",
        flexShrink: 0,
      }}
      onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "#f0f0f0" }}
      onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent" }}
    >
      {children}
      {badge !== undefined && (
        <div style={{
          position: "absolute", top: -5, right: -5,
          background: "#ff3b30", color: "#fff",
          fontSize: 9, fontWeight: 700,
          borderRadius: 8, minWidth: 16, height: 16,
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: "0 3px", lineHeight: 1,
        }}>
          {badge}
        </div>
      )}
    </div>
  )
}

function IconChat({ active }: { active?: boolean }) {
  const c = active ? "#07c160" : "#191919"
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function IconProfile({ active }: { active?: boolean }) {
  const c = active ? "#07c160" : "#999"
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}

function IconAcademy({ active }: { active?: boolean }) {
  const c = active ? "#07c160" : "#999"
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 22 8.5 12 15 2 8.5 12 2" />
      <path d="M6 11.5v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5" />
      <line x1="22" y1="8.5" x2="22" y2="14.5" />
    </svg>
  )
}

function IconSettings({ active }: { active?: boolean }) {
  const c = active ? "#07c160" : "#999"
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}
