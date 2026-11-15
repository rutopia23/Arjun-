# Railway worker image. Root Directory = services/voice-agent. The code lives at /srv/services/voice-agent because
# agent.py/applog.py/turnlog.py resolve the repo root as parents[2] (logs/ and eval/results/ go under /srv).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/services/voice-agent
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /srv/logs /srv/eval/results
ENV PYTHONUNBUFFERED=1
CMD ["python", "agent.py", "start"]
