FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    iperf3 openssh-client curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pppoe_monitor.py .

CMD ["python3", "pppoe_monitor.py"]
