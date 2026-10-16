# 本体(FastAPI)のイメージ。ビルドコンテキストは app/
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tokyo

WORKDIR /app

# ライブラリの版は constraints.txt で固定する(本体・モデル作成と同じ版)
COPY constraints.txt ./
COPY backend/pyproject.toml backend/
COPY backend/smdx_api backend/smdx_api
RUN pip install --no-cache-dir -c constraints.txt -e ./backend

COPY backend backend
WORKDIR /app/backend

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn --factory smdx_api.main:create_app --host 0.0.0.0 --port 8000"]
