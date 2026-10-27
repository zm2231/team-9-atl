# One Cloud Run service: the ADK agent API plus the built frontend (plan R1, R9).
# Lives at the repo root so `gcloud run deploy --source .` finds it.

FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/agent
COPY agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
EXPOSE 8080
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
