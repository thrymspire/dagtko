# DAG MCP Tool Server + LLM grounding adapter
FROM python:3.12-slim

WORKDIR /app

COPY mcp/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp/ /app/mcp/
COPY llm/ /app/llm/
COPY dynamic_dag/ /app/dynamic_dag/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
EXPOSE 8001

CMD ["uvicorn", "mcp.server:app", "--host", "0.0.0.0", "--port", "8001"]

