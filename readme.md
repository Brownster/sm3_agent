# SM3 Monitoring Agent

A modular chat assistant that connects a Grafana MCP server with LangChain tooling. The project ships a FastAPI backend and a Chainlit UI, keeping tools and LLM orchestration DRY and extensible.

## Structure
- `backend/app`: FastAPI entrypoint and configuration.
- `backend/agents`: Agent orchestration and memory helpers.
- `backend/tools`: MCP client and LangChain tool wrappers.
- `backend/schemas`: Pydantic schemas for chat requests/responses.
- `backend/utils`: Logging and prompts.
- `frontend/chainlit_app.py`: Lightweight chat UI reusing the backend agent.

## Getting started
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set required environment variables:
   ```bash
   export OPENAI_API_KEY=<your-key>
   export MCP_SERVER_URL=http://localhost:3001/mcp  # adjust to your MCP endpoint
   ```
3. Run the FastAPI service:
   ```bash
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Run the Chainlit UI (reuses the same agent stack):
   ```bash
   chainlit run frontend/chainlit_app.py
   ```

The API exposes `POST /api/chat` for chat turns and `GET /health` for readiness checks.

## Docker
- Build locally from the root Dockerfile:
  ```bash
  docker build -t sm3-agent:local .
  docker run --rm -p 8000:8000 \
    -e OPENAI_API_KEY=<your-key> \
    -e MCP_SERVER_URL=http://mcp:3001/mcp \
    sm3-agent:local
  ```
- Publish to GHCR via the "Manual Docker Build" GitHub Action. Trigger the workflow with a `version` input (e.g., `v0.1.0`) to build and push `ghcr.io/<org>/<repo>:<version>` using the same Dockerfile.

### Example docker-compose
The example assumes an MCP server is reachable at `http://mcp:3001/mcp` (run it as another service or adjust the URL).
```yaml
services:
  backend:
    image: ghcr.io/<org>/<repo>:<tag>
    restart: unless-stopped
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      MCP_SERVER_URL: http://mcp:3001/mcp
    ports:
      - "8000:8000"

  chainlit:
    image: ghcr.io/<org>/<repo>:<tag>
    command: ["chainlit", "run", "frontend/chainlit_app.py", "-h", "0.0.0.0", "-p", "8001"]
    restart: unless-stopped
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      MCP_SERVER_URL: http://mcp:3001/mcp
    depends_on:
      - backend
    ports:
      - "8001:8001"
```
