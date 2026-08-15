"""SQLAlchemy ORM models for Users, Settings, Reminders, Schedules, and Notifications."""

import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.utils.datetime_utils import utc_now


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    timezone = Column(String(64), default="Europe/Moscow", nullable=False)
    language = Column(String(10), default="ru", nullable=False)
    time_format = Column(String(10), default="24h", nullable=False)  # "24h" or "12h"
    first_day_of_week = Column(Integer, default=0, nullable=False)  # 0=Monday, 6=Sunday
    quiet_hours_enabled = Column(Boolean, default=False, nullable=False)
    quiet_start = Column(String(10), nullable=True, default="23:00")
    quiet_end = Column(String(10), nullable=True, default="07:00")
    quiet_action = Column(String(20), default="silent", nullable=False)  # "silent" or "delay"
    notifications_enabled = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="settings")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    due_at = Column(DateTime, nullable=False, index=True)  # UTC naive
    timezone = Column(String(64), default="Europe/Moscow", nullable=False)
    status = Column(String(30), default="ACTIVE", nullable=False, index=True)  # ACTIVE, COMPLETED, SNOOZED, CANCELLED, PAUSED
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurrence_rule = Column(String(255), nullable=True)  # e.g., "DAILY", "WEEKLY;BYDAY=MO,FR", "INTERVAL;HOURS=2"
    recurrence_end_at = Column(DateTime, nullable=True)
    is_last_context = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="reminders")
    schedules = relationship("ReminderSchedule", back_populates="reminder", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="reminder", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_due_status", "due_at", "status"),
        Index("idx_user_status", "user_id", "status"),
    )


class ReminderSchedule(Base):
    __tablename__ = "reminder_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False, index=True)
    rrule_str = Column(String(255), nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)

    reminder = relationship("Reminder", back_populates="schedules")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String(30), default="PENDING", nullable=False, index=True)  # PENDING, SENT, FAILED
    error_message = Column(Text, nullable=True)

    reminder = relationship("Reminder", back_populates="notifications")
    user = relationship("User", back_populates="notifications")
