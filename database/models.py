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
    created_at = Column(DateTime, default=datetime.utcnow)