import csv
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Review
from .schemas import (
    AnalyzeResult,
    BatchReviewCreate,
    KeywordItem,
    MessageResponse,
    ReviewCreate,
    ReviewResponse,
    StatsResponse,
)
from .seed_data import SAMPLE_REVIEWS
from .sentiment import analyze_text, extract_keywords, sentiment_label

Base.metadata.create_all(bind=engine)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

app = FastAPI(
    title="电商评论情感分析平台",
    description="基于 SnowNLP 的电商用户评论情感倾向分析系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_database(db: Session) -> int:
    if db.query(Review).count() > 0:
        return 0

    created = 0
    for product_name, content in SAMPLE_REVIEWS:
        score, sentiment = analyze_text(content)
        db.add(
            Review(
                product_name=product_name,
                content=content,
                score=score,
                sentiment=sentiment,
                source="sample",
            )
        )
        created += 1
    db.commit()
    return created


@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "sentiment-analysis-platform"}


@app.post("/api/analyze", response_model=AnalyzeResult)
def analyze_single(payload: ReviewCreate):
    score, sentiment = analyze_text(payload.content)
    keywords = [word for word, _ in extract_keywords([payload.content], top_k=8)]
    return AnalyzeResult(
        content=payload.content,
        score=score,
        sentiment=sentiment,
        keywords=keywords,
    )


@app.post("/api/reviews", response_model=ReviewResponse)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    score, sentiment = analyze_text(payload.content)
    review = Review(
        product_name=payload.product_name.strip() or "未分类商品",
        content=payload.content.strip(),
        score=score,
        sentiment=sentiment,
        source="manual",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@app.post("/api/reviews/batch", response_model=MessageResponse)
def create_reviews_batch(payload: BatchReviewCreate, db: Session = Depends(get_db)):
    if not payload.reviews:
        raise HTTPException(status_code=400, detail="评论列表不能为空")

    for item in payload.reviews:
        content = item.content.strip()
        if not content:
            continue
        score, sentiment = analyze_text(content)
        db.add(
            Review(
                product_name=item.product_name.strip() or "未分类商品",
                content=content,
                score=score,
                sentiment=sentiment,
                source="batch",
            )
        )
    db.commit()
    count = len(payload.reviews)
    return MessageResponse(message="批量分析完成", count=count)


@app.post("/api/reviews/upload", response_model=MessageResponse)
async def upload_reviews(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="ignore")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV 文件格式不正确")

    content_key = None
    product_key = None
    for name in reader.fieldnames:
        lower = name.lower().strip()
        if lower in {"content", "评论", "评论内容", "review", "text"}:
            content_key = name
        if lower in {"product_name", "商品", "商品名称", "product", "name"}:
            product_key = name

    if not content_key:
        content_key = reader.fieldnames[0]

    count = 0
    for row in reader:
        content = (row.get(content_key) or "").strip()
        if not content:
            continue
        product_name = (row.get(product_key) or "未分类商品").strip() if product_key else "未分类商品"
        score, sentiment = analyze_text(content)
        db.add(
            Review(
                product_name=product_name,
                content=content,
                score=score,
                sentiment=sentiment,
                source="upload",
            )
        )
        count += 1

    if count == 0:
        raise HTTPException(status_code=400, detail="未从文件中解析到有效评论")

    db.commit()
    return MessageResponse(message="文件导入并分析完成", count=count)


@app.get("/api/reviews", response_model=List[ReviewResponse])
def list_reviews(
    sentiment: Optional[str] = Query(default=None),
    product_name: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Review).order_by(Review.created_at.desc())

    if sentiment in {"positive", "neutral", "negative"}:
        query = query.filter(Review.sentiment == sentiment)
    if product_name:
        query = query.filter(Review.product_name.contains(product_name))
    if keyword:
        query = query.filter(Review.content.contains(keyword))

    return query.limit(limit).all()


@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="评论不存在")
    return review


@app.delete("/api/reviews/{review_id}", response_model=MessageResponse)
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="评论不存在")
    db.delete(review)
    db.commit()
    return MessageResponse(message="删除成功")


@app.delete("/api/reviews", response_model=MessageResponse)
def clear_reviews(db: Session = Depends(get_db)):
    count = db.query(Review).delete()
    db.commit()
    return MessageResponse(message="已清空全部评论", count=count)


@app.post("/api/seed", response_model=MessageResponse)
def reload_sample_data(db: Session = Depends(get_db)):
    db.query(Review).delete()
    db.commit()
    count = seed_database(db)
    return MessageResponse(message="示例数据已重新加载", count=count)


@app.get("/api/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    reviews = db.query(Review).all()
    total = len(reviews)
    positive = sum(1 for r in reviews if r.sentiment == "positive")
    neutral = sum(1 for r in reviews if r.sentiment == "neutral")
    negative = sum(1 for r in reviews if r.sentiment == "negative")
    average_score = round(sum(r.score for r in reviews) / total, 4) if total else 0.0

    product_rows = (
        db.query(
            Review.product_name,
            func.count(Review.id).label("count"),
            func.avg(Review.score).label("avg_score"),
        )
        .group_by(Review.product_name)
        .order_by(func.count(Review.id).desc())
        .all()
    )

    product_stats = [
        {
            "product_name": row.product_name,
            "count": row.count,
            "average_score": round(float(row.avg_score), 4),
        }
        for row in product_rows
    ]

    trend_map = {}
    for review in reviews:
        day = review.created_at.strftime("%Y-%m-%d")
        if day not in trend_map:
            trend_map[day] = {"date": day, "positive": 0, "neutral": 0, "negative": 0}
        trend_map[day][review.sentiment] += 1

    recent_trend = sorted(trend_map.values(), key=lambda x: x["date"])[-14:]

    if not recent_trend and total:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        recent_trend = [
            {
                "date": today,
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
            }
        ]

    return StatsResponse(
        total=total,
        positive=positive,
        neutral=neutral,
        negative=negative,
        average_score=average_score,
        product_stats=product_stats,
        recent_trend=recent_trend,
    )


@app.get("/api/keywords", response_model=List[KeywordItem])
def get_keywords(
    sentiment: Optional[str] = Query(default=None),
    top_k: int = Query(default=20, ge=5, le=50),
    db: Session = Depends(get_db),
):
    query = db.query(Review)
    if sentiment in {"positive", "neutral", "negative"}:
        query = query.filter(Review.sentiment == sentiment)
    texts = [r.content for r in query.all()]
    return [KeywordItem(word=word, count=count) for word, count in extract_keywords(texts, top_k)]


@app.get("/api/export")
def export_reviews(
    sentiment: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Review).order_by(Review.created_at.desc())
    if sentiment in {"positive", "neutral", "negative"}:
        query = query.filter(Review.sentiment == sentiment)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "商品名称", "评论内容", "情感得分", "情感倾向", "来源", "创建时间"])
    for review in query.all():
        writer.writerow(
            [
                review.id,
                review.product_name,
                review.content,
                review.score,
                sentiment_label(review.sentiment),
                review.source,
                review.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

    output.seek(0)
    filename = f"sentiment_reviews_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/sample-csv")
def download_sample_csv():
    sample_path = DATA_DIR / "sample_reviews.csv"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="样例文件不存在")
    return FileResponse(sample_path, filename="sample_reviews.csv", media_type="text/csv")


@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="前端页面未找到")
    return FileResponse(index_path)


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
