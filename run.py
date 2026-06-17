#!/usr/bin/env python3
"""启动电商评论情感分析平台"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
