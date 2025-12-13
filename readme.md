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
