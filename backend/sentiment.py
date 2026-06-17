import re
from collections import Counter
from typing import Iterable, List, Tuple

import jieba
from snownlp import SnowNLP

POSITIVE_THRESHOLD = 0.6
NEGATIVE_THRESHOLD = 0.4

STOP_WORDS = {
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "他", "她", "它", "我们", "你们", "他们", "这个", "那个",
    "什么", "怎么", "还是", "可以", "但是", "因为", "所以", "如果", "已经", "非常",
    "比较", "感觉", "真的", "还是", "还是", "还是", "还是", "还是", "还是",
    "商品", "东西", "产品", "购买", "收到", "快递", "包装", "卖家", "店铺",
}


def clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def score_to_sentiment(score: float) -> str:
    if score >= POSITIVE_THRESHOLD:
        return "positive"
    if score <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def sentiment_label(sentiment: str) -> str:
    mapping = {
        "positive": "正面",
        "neutral": "中性",
        "negative": "负面",
    }
    return mapping.get(sentiment, sentiment)


def analyze_text(content: str) -> Tuple[float, str]:
    cleaned = clean_text(content)
    if not cleaned:
        return 0.5, "neutral"
    score = float(SnowNLP(cleaned).sentiments)
    return round(score, 4), score_to_sentiment(score)


def extract_keywords(texts: Iterable[str], top_k: int = 20) -> List[Tuple[str, int]]:
    counter: Counter[str] = Counter()
    for text in texts:
        words = jieba.lcut(clean_text(text))
        for word in words:
            if len(word) < 2:
                continue
            if word in STOP_WORDS:
                continue
            if re.fullmatch(r"[\W\d_]+", word):
                continue
            counter[word] += 1
    return counter.most_common(top_k)
