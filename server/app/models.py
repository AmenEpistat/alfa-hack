from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    initials: Mapped[str] = mapped_column(String(10), nullable=False)
    role: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    questions: Mapped[list["QuestionHistory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    ranking_items: Mapped[list["RankingItem"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )

    purchase_plan: Mapped[list["PurchasePlan"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    cover: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    sections: Mapped[list["InsightSection"]] = relationship(
        back_populates="insight",
        cascade="all, delete-orphan",
        order_by="InsightSection.position",
    )

    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="insight",
        cascade="all, delete-orphan",
    )


class InsightSection(Base):
    __tablename__ = "insight_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    insight_id: Mapped[str] = mapped_column(
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    insight: Mapped["Insight"] = relationship(
        back_populates="sections",
    )


class PurchasePlan(Base):
    __tablename__ = "purchase_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month: Mapped[str] = mapped_column(String(20), nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    fixed_volume: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    company: Mapped["Company"] = relationship(
        back_populates="purchase_plan",
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insight_id: Mapped[str] = mapped_column(
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_saved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    feedback: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    feedback_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="preferences",
    )

    insight: Mapped["Insight"] = relationship(
        back_populates="preferences",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "insight_id",
            name="uq_user_insight_preference",
        ),
    )


class QuestionHistory(Base):
    __tablename__ = "question_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insight_id: Mapped[str] = mapped_column(
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="questions",
    )


class RankingRun(Base):
    __tablename__ = "ranking_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    company_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    topic: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    schema_version: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    request_payload: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    result_payload: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    diagnostics: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    items: Mapped[list["RankingItem"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )

    sets: Mapped[list["RankingSetRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class RankingItem(Base):
    __tablename__ = "ranking_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    run_id: Mapped[int] = mapped_column(
        ForeignKey("ranking_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    item_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    document_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    kind: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    payload: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    run: Mapped["RankingRun"] = relationship(
        back_populates="items",
    )

    company: Mapped["Company | None"] = relationship(
        back_populates="ranking_items",
    )


class RankingSetRecord(Base):
    __tablename__ = "ranking_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    run_id: Mapped[int] = mapped_column(
        ForeignKey("ranking_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    set_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    company_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    set_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    payload: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    run: Mapped["RankingRun"] = relationship(
        back_populates="sets",
    )
