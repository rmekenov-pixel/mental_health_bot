from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    reminder_time = Column(String, nullable=True, default="20:00")
    utc_offset = Column(Integer, nullable=True, default=5)
    language = Column(String, nullable=True, default="ru")
    created_at = Column(DateTime, default=datetime.utcnow)

class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    test_name = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    level = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CheckIn(Base):
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    mood = Column(Integer, nullable=False)
    anxiety = Column(Integer, nullable=False)
    energy = Column(Integer, nullable=False)
    sleep_hours = Column(Integer, nullable=True)
    sleep_quality = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserStreak(Base):
    __tablename__ = "streaks"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_checkin_date = Column(DateTime, nullable=True)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    rating = Column(String, nullable=False)  # "positive" или "negative"
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)