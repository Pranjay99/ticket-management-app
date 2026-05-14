# ── Stage 1: Build React ──────────────────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /app/react-frontend
COPY react-frontend/package*.json ./
RUN npm install
COPY react-frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + React dist ─────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# System deps for SQLite (already in slim, but keep gcc for any native wheels)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy sample data (used for auto-seeding and download)
COPY data/ ./data/

# Copy React build output from stage 1
COPY --from=frontend /app/react-frontend/dist ./react-frontend/dist

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
