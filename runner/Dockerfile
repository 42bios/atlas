FROM python:3.13-alpine
RUN apk add --no-cache docker-cli && addgroup -g 1000 runner && adduser -D -u 1000 -G runner runner
COPY runner/service.py /runner.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
CMD ["python", "/runner.py"]
