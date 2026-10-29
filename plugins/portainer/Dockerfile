FROM python:3.13-alpine
WORKDIR /plugin
RUN addgroup -g 1000 plugin && adduser -D -u 1000 -G plugin plugin
COPY collector.py runtime.py ./
USER plugin
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "runtime.py"]
