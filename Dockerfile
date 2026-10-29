FROM python:3.13-alpine
WORKDIR /app
RUN addgroup -g 1000 atlas && adduser -D -u 1000 -G atlas atlas && mkdir /data && chown atlas:atlas /data
RUN pip install --no-cache-dir Pillow==11.3.0
COPY server.py inventory_model.py connector_engine.py vssx_import.py device_catalog.py plugin_api.py connector_setup.py addin_manager.py ./
COPY atlas_core ./atlas_core
COPY atlas_modules ./atlas_modules
COPY plugins ./plugins
COPY static ./static
COPY docs/handbook ./docs/handbook
COPY scripts ./scripts
COPY LICENSE THIRD_PARTY_NOTICES.md VERSION ./
USER atlas
ENV ATLAS_DB=/data/atlas.db ATLAS_CONNECTORS=/connectors PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/connectors',timeout=2)"
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8765"]
