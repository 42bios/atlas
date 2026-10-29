FROM python:3.13-alpine
RUN apk add --no-cache net-snmp-tools && addgroup -g 1000 worker && adduser -D -u 1000 -G worker worker
COPY runner/bootstrap.py /bootstrap.py
USER 1000:1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/bootstrap.py"]
