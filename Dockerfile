FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py glama.json README.md LICENSE ./

# MCP stdio transport — Glama/registry runs this and talks over stdin/stdout.
ENTRYPOINT ["python", "server.py"]
