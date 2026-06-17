from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(128), nullable=False, default="未分类商品")
    content = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    sentiment = Column(String(16), nullable=False)
    source = Column(String(32), nullable=False, default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)
