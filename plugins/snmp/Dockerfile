FROM python:3.13-alpine
WORKDIR /app
RUN apk add --no-cache net-snmp-tools && adduser -D -u 1000 connector
COPY plugins/common /app/common
COPY plugins/snmp/collector.py plugins/snmp/runtime.py /app/
USER connector
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "runtime.py"]
