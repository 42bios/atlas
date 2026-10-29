FROM python:3.13-alpine
WORKDIR /app
RUN adduser -D -u 1000 connector
COPY plugins/common /app/common
COPY plugins/kubernetes/collector.py plugins/kubernetes/runtime.py /app/
USER connector
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "runtime.py"]
