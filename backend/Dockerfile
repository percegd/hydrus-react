FROM python:3.11-slim
WORKDIR /app
COPY packages/hydrus-core ./packages/hydrus-core
RUN pip install --no-cache-dir ./packages/hydrus-core
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
