FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    ca-certificates \
    tar \
 && rm -rf /var/lib/apt/lists/* \
 && wget -O /tmp/piper.tar.gz https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x86_64.tar.gz \
 && tar -xzf /tmp/piper.tar.gz -C /tmp \
 && mv /tmp/piper/piper /usr/local/bin/piper \
 && chmod +x /usr/local/bin/piper \
 && rm -rf /tmp/piper /tmp/piper.tar.gz


COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-5001} review_snippets:app"]
