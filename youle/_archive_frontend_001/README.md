# `_archive_frontend_001` — 已归档

这个目录是 v0 生成的视觉原型,**不再维护**。

视觉资产已经迁移到主前端 `youle/frontend/`:

| 旧文件 | 现在的位置 |
| --- | --- |
| `app/page.tsx`(四栏布局) | `frontend/components/layout/AppShell.tsx` |
| `components/wechat/sidebar.tsx` | `frontend/components/layout/AppSidebar.tsx` |
| `components/wechat/chat-list.tsx` | `frontend/components/layout/ChatList.tsx` |
| `components/wechat/chat-window.tsx` | `frontend/components/chat/{ChatPanel,ChatHeader,MessageList,MessageBubble,TaskCard,Composer}.tsx` |
| `components/wechat/agent-panel.tsx` | `frontend/components/layout/AgentPanel.tsx` |
| `public/team-avatar.png` 等 | `frontend/public/` |

迁移要点:
- 内联 `style={{...}}` → Tailwind class(铁律 §3 frontend)
- 硬编码 `INITIAL_MESSAGES / TASKS / CHATS` → Zustand stores + TanStack Query(`useConversations / useMessages / useMembers`)
- 接 WebSocket 推送(`message_added` / `step_*` / `agent_status_changed` / `work_mode_changed`)
- 补齐 V1 必做:ModeSwitcher / GroupMembers / OnboardingFlow / HITL 三组件 / EmojiPicker

如需恢复参考,只看不要改。
