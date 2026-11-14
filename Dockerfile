# One container: builds the web app, serves it + the API on :7860 (Azure Container Apps; image built by GitHub Actions).
FROM node:22-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
# Run as uid 1000 (also what Hugging Face Spaces expects): own everything the app writes (data/, ~/.duckdb extensions)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /app
COPY --chown=user server/requirements.txt server/
RUN pip install --no-cache-dir --user -r server/requirements.txt \
 && python -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL spatial; INSTALL httpfs')"
COPY --chown=user server/ server/
COPY --chown=user data/regions/ data/regions/
# independent validation results (NASA burned area, APAD kiln inventory), with their attribution
COPY --chown=user data/validation/ data/validation/
# 30-day outlook snapshot (rebuilt daily where the global aggregate exists; served as-is otherwise)
COPY --chown=user data/global/outlook.json data/global/outlook.json
# Worldwide fire months per 0.1-degree cell (10 MB): "Is fire near you?" for any place without the 1.7 GB aggregate
COPY --chown=user data/global/fire_season.parquet data/global/fire_season.parquet
COPY --chown=user data/sensor_days.parquet data/sensor_days.parquet
# Aqua drift onset: live builds must leave out drifting Aqua exactly like the prebuilt areas
COPY --chown=user data/aqua_overpass.json data/aqua_overpass.json
COPY --chown=user --from=web /web/dist web/dist
ENV KW_DATA=/app/data KW_PUBLIC_MCP=1 PYTHONUNBUFFERED=1
WORKDIR /app/server
EXPOSE 7860
CMD ["uvicorn", "kw.api:app", "--host", "0.0.0.0", "--port", "7860"]
