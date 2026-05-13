# -*- coding: utf-8 -*-
"""
AILife SQLAlchemy 数据库模型 - NorthFrank 适配版

使用 SQLAlchemy 2.0 风格（DeclarativeBase + Mapped + mapped_column）
定义所有数据库表结构。

架构说明（NorthFrank 适配）：
- SQLAlchemy 模型用于数据库迁移（Alembic）和 ORM 定义
- 实际 CRUD 操作使用 asyncpg（app/db.py 的 Database 类）
- 向量类型在 SQL 层使用 pgvector 的 vector 类型，模型层保持 JSON/List 映射

表清单：
    speakers      - 说话人信息
    recordings    - 录音记录
    utterances    - 语音转写片段
    events        - 事件提取
    todos         - 待办事项
    flash_memos   - 闪念笔记
    bill_notes    - 账单记录
    chat_sessions - 聊天会话
    chat_messages - 聊天消息
    weekly_reports- 周报数据
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """声明式基类，所有模型的父类。"""

    pass


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _new_uuid() -> uuid.UUID:
    """生成新的 UUID4。"""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# speakers 表 - 说话人信息
# ---------------------------------------------------------------------------


class Speaker(Base):
    """说话人（Speaker）模型。

    记录系统中识别出的说话人信息，包括声纹特征向量、关系类型等。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        name: 说话人名称（可选）
        relation: 关系类型（同事/家人/朋友/未知）
        is_master: 是否为主人（机主）
        embedding: 声纹特征向量（192维，JSON 字符串存储）
        voice_sample_count: 语音样本数量
        first_met_at: 首次识别时间
        last_talk_at: 最后对话时间
        summary: 人物摘要
        created_at: 创建时间
    """

    __tablename__ = "speakers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    relation: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="同事/家人/朋友/未知",
    )
    is_master: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否为主人（机主）",
    )
    # pgvector Vector(192) — SQLAlchemy 不原生支持 vector，
    # 使用 String 类型存储 JSON 字符串，在应用层进行序列化/反序列化
    embedding: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="声纹特征向量 192维，JSON 数组字符串",
    )
    voice_sample_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    first_met_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_talk_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 关系定义
    utterances: Mapped[List["Utterance"]] = relationship(
        "Utterance",
        back_populates="speaker",
        cascade="all, delete-orphan",
    )
    todos: Mapped[List["Todo"]] = relationship(
        "Todo",
        back_populates="related_speaker",
        cascade="all, delete-orphan",
    )
    bill_notes: Mapped[List["BillNote"]] = relationship(
        "BillNote",
        back_populates="related_speaker",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<Speaker(id={self.id!r}, name={self.name!r}, "
            f"relation={self.relation!r}, is_master={self.is_master!r})>"
        )


# ---------------------------------------------------------------------------
# recordings 表 - 录音记录
# ---------------------------------------------------------------------------


class Recording(Base):
    """录音（Recording）模型。

    记录每次录音的基本信息，包括音频文件位置、时长、地点等。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        audio_url: 音频文件 URL
        duration_sec: 录音时长（秒）
        is_meeting_mode: 是否为会议模式
        location_lat: 纬度
        location_lng: 经度
        location_name: 地点名称
        summary: 录音内容摘要
        topics: 主题标签数组（JSON）
        created_at: 创建时间
    """

    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    audio_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    duration_sec: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    is_meeting_mode: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    location_lat: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    location_lng: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    location_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    topics: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="主题标签数组",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 关系定义
    utterances: Mapped[List["Utterance"]] = relationship(
        "Utterance",
        back_populates="recording",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<Recording(id={self.id!r}, duration={self.duration_sec!r}, "
            f"meeting_mode={self.is_meeting_mode!r})>"
        )


# ---------------------------------------------------------------------------
# utterances 表 - 语音转写片段
# ---------------------------------------------------------------------------


class Utterance(Base):
    """语音转写片段（Utterance）模型。

    记录录音中每个人的发言片段，包含时间戳、文本、情感等信息。

    Attributes:
        id: UUID 主键
        recording_id: 关联录音 UUID（外键）
        speaker_id: 关联说话人 UUID（外键，可选）
        start_sec: 开始时间（秒）
        end_sec: 结束时间（秒）
        text: 转写文本
        embedding: 文本向量（768维，JSON 数组）
        emotion: 情感类型（积极/中性/消极）
        is_master: 是否为主人发言
        created_at: 创建时间
    """

    __tablename__ = "utterances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    recording_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recordings.id", ondelete="CASCADE"),
        nullable=False,
    )
    speaker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_sec: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    end_sec: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # 768维向量存储为 JSON 数组
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        JSON,
        nullable=True,
        comment="768维文本向量，JSON 数组",
    )
    emotion: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="积极/中性/消极",
    )
    is_master: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 关系定义
    recording: Mapped["Recording"] = relationship(
        "Recording",
        back_populates="utterances",
    )
    speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker",
        back_populates="utterances",
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<Utterance(id={self.id!r}, recording={self.recording_id!r}, "
            f"text={self.text[:50]!r}...)>"
        )


# ---------------------------------------------------------------------------
# events 表 - 事件提取
# ---------------------------------------------------------------------------


class Event(Base):
    """事件（Event）模型。

    从对话中自动提取的关键事件，包括约定、待办、账单等。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        title: 事件标题
        event_date: 事件日期
        related_speaker_ids: 相关说话人 UUID 数组（JSON）
        source_utterance_ids: 来源语音片段 UUID 数组（JSON）
        event_type: 事件类型（约定/待办/账单/其他）
        status: 状态（默认 active）
        created_at: 创建时间
    """

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    event_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    related_speaker_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        JSON,
        nullable=True,
        comment="相关说话人 UUID 数组",
    )
    source_utterance_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        JSON,
        nullable=True,
        comment="来源语音片段 UUID 数组",
    )
    event_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="约定/待办/账单/其他",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<Event(id={self.id!r}, title={self.title!r}, "
            f"type={self.event_type!r}, status={self.status!r})>"
        )


# ---------------------------------------------------------------------------
# todos 表 - 待办事项
# ---------------------------------------------------------------------------


class Todo(Base):
    """待办事项（Todo）模型。

    从对话中自动提取的待办任务。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        title: 待办标题
        due_date: 截止日期
        source: 来源描述
        related_speaker_id: 相关说话人 UUID（外键）
        webhook_url: 提醒回调 URL
        status: 状态（默认 pending）
        created_at: 创建时间
    """

    __tablename__ = "todos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    related_speaker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 关系定义
    related_speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker",
        back_populates="todos",
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<Todo(id={self.id!r}, title={self.title!r}, "
            f"status={self.status!r})>"
        )


# ---------------------------------------------------------------------------
# flash_memos 表 - 闪念笔记
# ---------------------------------------------------------------------------


class FlashMemo(Base):
    """闪念笔记（FlashMemo）模型。

    快速记录的简短笔记，支持语音和标签。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        text: 笔记内容
        audio_url: 关联音频 URL（可选）
        tags: 标签数组（JSON）
        created_at: 创建时间
    """

    __tablename__ = "flash_memos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    audio_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="标签字符串数组",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<FlashMemo(id={self.id!r}, text={self.text[:50]!r}...), "
            f"tags={self.tags!r}>"
        )


# ---------------------------------------------------------------------------
# bill_notes 表 - 账单记录
# ---------------------------------------------------------------------------


class BillNote(Base):
    """账单记录（BillNote）模型。

    从对话中自动提取的账单/消费信息。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        amount: 金额
        currency: 货币（默认 CNY）
        category: 消费类别
        related_speaker_id: 相关说话人 UUID（外键）
        context: 上下文描述
        bill_date: 账单日期
        created_at: 创建时间
    """

    __tablename__ = "bill_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    amount: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="CNY",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    related_speaker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
    )
    context: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    bill_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 关系定义
    related_speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker",
        back_populates="bill_notes",
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<BillNote(id={self.id!r}, amount={self.amount!r} "
            f"{self.currency!r}, category={self.category!r})>"
        )


# ---------------------------------------------------------------------------
# chat_sessions 表 - 聊天会话
# ---------------------------------------------------------------------------


class ChatSession(Base):
    """聊天会话（ChatSession）模型。

    用户与 AI 助手的聊天会话记录。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        title: 会话标题
        context_summary: 上下文摘要
        created_at: 创建时间
    """

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    context_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 关系定义
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<ChatSession(id={self.id!r}, title={self.title!r}, "
            f"messages={len(self.messages) if self.messages else 0})>"
        )


# ---------------------------------------------------------------------------
# chat_messages 表 - 聊天消息
# ---------------------------------------------------------------------------


class ChatMessage(Base):
    """聊天消息（ChatMessage）模型。

    会话中的单条消息记录。

    Attributes:
        id: UUID 主键
        session_id: 关联会话 UUID（外键）
        role: 角色（user/assistant）
        content: 消息内容
        created_at: 创建时间
    """

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="user/assistant",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 关系定义
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<ChatMessage(id={self.id!r}, role={self.role!r}, "
            f"content={self.content[:50]!r}...)>"
        )


# ---------------------------------------------------------------------------
# weekly_reports 表 - 周报数据
# ---------------------------------------------------------------------------


class WeeklyReport(Base):
    """周报（WeeklyReport）模型。

    自动生成的每周总结报告。

    Attributes:
        id: UUID 主键
        user_id: 所属用户 UUID
        week_start: 周报开始日期
        week_end: 周报结束日期
        data_json: 周报数据（JSON 格式）
        tts_audio_url: TTS 合成音频 URL
        created_at: 创建时间
    """

    __tablename__ = "weekly_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    week_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    week_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    data_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="周报结构化数据",
    )
    tts_audio_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        """返回模型的字符串表示。"""
        return (
            f"<WeeklyReport(id={self.id!r}, "
            f"week={self.week_start!r} ~ {self.week_end!r})>"
        )
