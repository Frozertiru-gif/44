from __future__ import annotations

from datetime import date, datetime
from uuid import UUID as UUIDType
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Index, JSON, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.base import Base
from app.db.enums import AdSource, LeadAdSource, LeadStatus, ProjectTransactionType, TicketCategory, TicketStatus, TransferStatus, UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    master_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    admin_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    created_tickets = relationship(
        "Ticket",
        back_populates="created_by",
        foreign_keys="Ticket.created_by_admin_id",
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(8), nullable=False, unique=True, index=True)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus, name="ticket_status"))
    category: Mapped[TicketCategory] = mapped_column(Enum(TicketCategory, name="ticket_category"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    preferred_date_dm: Mapped[str | None] = mapped_column(String(5), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_age_estimate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    client_phone: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_text: Mapped[str] = mapped_column(Text, nullable=False)
    special_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ad_source: Mapped[AdSource] = mapped_column(Enum(AdSource, name="ad_source"), default=AdSource.UNKNOWN)
    is_repeat: Mapped[bool] = mapped_column(Boolean, default=False)
    repeat_ticket_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    created_by_admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_by = relationship("User", back_populates="created_tickets", foreign_keys=[created_by_admin_id])

    assigned_executor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    assigned_executor = relationship("User", foreign_keys=[assigned_executor_id])
    assigned_worker_id: Mapped[int | None] = synonym("assigned_executor_id")
    taken_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    closed_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_photo_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expense: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    net_profit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    transfer_status: Mapped[TransferStatus | None] = mapped_column(
        Enum(TransferStatus, name="transfer_status"), nullable=True
    )
    transfer_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transfer_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transfer_confirmed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    junior_master_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    junior_master_percent_at_close: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    junior_master_earned_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    executor_percent_at_close: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    admin_percent_at_close: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    executor_earned_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    admin_earned_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    project_take_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    transfer_confirmer = relationship("User", foreign_keys=[transfer_confirmed_by])
    closed_by_user = relationship("User", foreign_keys=[closed_by_user_id])
    junior_master = relationship("User", foreign_keys=[junior_master_id])

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("TicketEvent", back_populates="ticket")
    close_photos = relationship(
        "TicketClosePhoto",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketClosePhoto.id",
    )


class TicketClosePhoto(Base):
    __tablename__ = "ticket_close_photos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tickets.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(Text, nullable=False)
    file_unique_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="close_photos")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_status_created_at", "status", text("created_at DESC")),
        Index(
            "ix_leads_client_phone_created_at",
            "client_phone",
            text("created_at DESC"),
            postgresql_where=text("client_phone IS NOT NULL"),
        ),
    )

    id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preferred_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    client_age_estimate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    problem_text: Mapped[str] = mapped_column(Text, nullable=False)
    special_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ad_source: Mapped[LeadAdSource | None] = mapped_column(Enum(LeadAdSource, name="lead_ad_source"), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus, name="lead_status"), nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    converted_ticket_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tickets.id"), nullable=True)

    converted_ticket = relationship("Ticket", foreign_keys=[converted_ticket_id])


class DailyCounter(Base):
    __tablename__ = "daily_counters"

    counter_date: Mapped[date] = mapped_column(Date, primary_key=True)
    counter: Mapped[int] = mapped_column(BigInteger, nullable=False)


class MasterJuniorLink(Base):
    __tablename__ = "master_junior_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    master_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    junior_master_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    master = relationship("User", foreign_keys=[master_id])
    junior_master = relationship("User", foreign_keys=[junior_master_id])


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tickets.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="events")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectTransaction(Base):
    __tablename__ = "project_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[ProjectTransactionType] = mapped_column(
        Enum(ProjectTransactionType, name="project_transaction_type"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by])


class ProjectShare(Base):
    __tablename__ = "project_shares"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    set_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    set_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    setter = relationship("User", foreign_keys=[set_by])


class ProjectSettings(Base):
    __tablename__ = "project_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requests_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="RUB")
    rounding_mode: Mapped[str] = mapped_column(String(32), default="HALF_UP")
    thresholds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
