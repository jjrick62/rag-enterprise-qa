"""多轮对话管理——session 创建/追加/裁剪

策略：
  - 内存存储（进程重启丢失，够 demo 用）
  - 每轮保留最近 N 条历史消息
  - 注入 Prompt 时控制总长度，防止上下文溢出
"""
from dataclasses import dataclass, field
from typing import Dict, List
import time


@dataclass
class Message:
    role: str       # "user" | "assistant"
    content: str    # 对 assistant 只存前 300 字的摘要（省 token）
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class ConversationManager:
    """会话管理器——创建、追加、获取历史"""

    MAX_HISTORY_ROUNDS = 5   # 最多保留 5 轮对话
    MAX_CONTENT_LEN = 300    # 每条消息截断长度（省 token）

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str):
        session = self.get_or_create(session_id)
        session.messages.append(Message(role="user", content=user_msg))
        # 助理回答只保存摘要（全文太长，会撑爆 context）
        session.messages.append(Message(
            role="assistant",
            content=assistant_msg[:self.MAX_CONTENT_LEN],
        ))
        # 裁剪：保留最近 N 轮
        if len(session.messages) > self.MAX_HISTORY_ROUNDS * 2:
            session.messages = session.messages[-(self.MAX_HISTORY_ROUNDS * 2):]

    def get_history(self, session_id: str) -> List[Message]:
        session = self._sessions.get(session_id)
        return session.messages.copy() if session else []

    def build_history_block(self, session_id: str) -> str:
        """构建注入 Prompt 的历史对话块

        格式：
          【对话历史】
          用户：上次问的问题
          助理：上次回答的摘要
          ---
          用户：当前问题
        """
        history = self.get_history(session_id)
        if not history:
            return ""

        lines = ["【对话历史】"]
        for msg in history:
            role_label = "用户" if msg.role == "user" else "助理"
            lines.append(f"{role_label}：{msg.content}")
        return "\n".join(lines) + "\n\n"

    def delete_session(self, session_id: str):
        self._sessions.pop(session_id, None)
