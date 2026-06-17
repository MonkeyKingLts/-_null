from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    product_name: str = Field(default="未分类商品", max_length=128)


class BatchReviewItem(BaseModel):
    content: str
    product_name: str = "未分类商品"


class BatchReviewCreate(BaseModel):
    reviews: List[BatchReviewItem]


class ReviewResponse(BaseModel):
    id: int
    product_name: str
    content: str
    score: float
    sentiment: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyzeResult(BaseModel):
    content: str
    score: float
    sentiment: str
    keywords: List[str]


class StatsResponse(BaseModel):
    total: int
    positive: int
    neutral: int
    negative: int
    average_score: float
    product_stats: List[dict]
    recent_trend: List[dict]


class KeywordItem(BaseModel):
    word: str
    count: int


class MessageResponse(BaseModel):
    message: str
    count: Optional[int] = None
