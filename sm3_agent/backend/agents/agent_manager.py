from __future__ import annotations

from typing import Dict, List

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.agents import Tool as LangChainTool
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from backend.app.config import Settings
from backend.agents.suggestions import get_suggestion_engine
from backend.schemas.models import AgentResult
from backend.tools.tool_wrappers import build_mcp_tools
from backend.utils.logger import get_logger
from backend.utils.prompts import SYSTEM_PROMPT


logger = get_logger(__name__)
suggestion_engine = get_suggestion_engine()


class AgentManager:
    """Orchestrates LLM calls, tools, and per-session memory using modern LangChain patterns."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = ChatOpenAI(
            model=settings.model,
            temperature=0.1,
            api_key=settings.openai_api_key,
            streaming=True  # Enable streaming for better UX
        )
        self.tools: List[LangChainTool] = []
        self._initialized = False

        # Store separate memory for each session
        self.session_memories: Dict[str, ConversationBufferMemory] = {}

        # Prompt for tool-calling agent (no ReAct text parsing)
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                SYSTEM_PROMPT + "\n\nYou have access to the registered MCP tools. Use them when helpful."
            ),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

    async def initialize(self) -> None:
        """
        Initialize the agent with MCP tools.

        This must be called before run_chat. It's separate from __init__
        because tool discovery is async.
        """
        if self._initialized:
            return

        logger.info("Initializing agent with MCP tools")
        self.tools = await build_mcp_tools(settings=self.settings)
        logger.info(f"Agent initialized with {len(self.tools)} tools")
        self._initialized = True

    def get_or_create_memory(self, session_id: str) -> ConversationBufferMemory:
        """
        Get or create memory for a specific session.

        Each session gets its own isolated conversation history.
        """
        if session_id not in self.session_memories:
            logger.info(f"Creating new memory for session: {session_id}")
            self.session_memories[session_id] = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="output"
            )
        return self.session_memories[session_id]


    def create_agent_executor(self, memory: ConversationBufferMemory) -> AgentExecutor:
        """
        Create a ReAct agent executor with the given memory.

        Uses the modern create_react_agent pattern instead of deprecated initialize_agent.
        """
        # Create the tool-calling agent to avoid brittle ReAct parsing
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        # Wrap in AgentExecutor for execution
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=memory,
            verbose=self.settings.enable_tracing,
            handle_parsing_errors=True,
            max_iterations=10,  # Prevent infinite loops
            max_execution_time=60,  # 60 second timeout
            return_intermediate_steps=True  # Return tool calls for logging
        )

        return agent_executor

    async def run_chat(self, message: str, session_id: str | None) -> AgentResult:
        """
        Execute a chat turn and return the agent response.

        Args:
            message: User message to process
            session_id: Session identifier for conversation isolation

        Returns:
            AgentResult with the response and any tool calls
        """
        # Ensure agent is initialized
        if not self._initialized:
            await self.initialize()

        # Use a default session if none provided
        if session_id is None:
            session_id = "default"

        # Get session-specific memory
        memory = self.get_or_create_memory(session_id)

        # Create agent executor with session-specific memory
        agent_executor = self.create_agent_executor(memory)

        logger.info(f"Processing message for session: {session_id}")

        try:
            # Execute the agent
            result = await agent_executor.ainvoke({"input": message})

            # Extract the response
            response = result.get("output", "")

            # Extract tool calls from intermediate steps
            tool_calls = []
            last_tool_name = None
            last_tool_args = {}
            last_result = None

            if "intermediate_steps" in result:
                for step in result["intermediate_steps"]:
                    if len(step) >= 2:
                        action, observation = step[0], step[1]
                        tool_calls.append({
                            "tool": action.tool,
                            "input": action.tool_input,
                            "output": str(observation)[:200]  # Truncate for logging
                        })

                        # Track last tool for suggestions
                        last_tool_name = action.tool
                        last_tool_args = action.tool_input if isinstance(action.tool_input, dict) else {}
                        last_result = observation

            # Generate suggestions based on tool usage
            suggestions = []
            if last_tool_name:
                suggestions = suggestion_engine.generate_suggestions(
                    tool_name=last_tool_name,
                    tool_args=last_tool_args,
                    result=last_result,
                    message=message
                )

            logger.info(f"Completed processing for session {session_id}, used {len(tool_calls)} tools, generated {len(suggestions)} suggestions")

            return AgentResult(message=response, tool_calls=tool_calls, suggestions=suggestions)

        except Exception as e:
            logger.error(f"Error executing agent: {e}", exc_info=True)
            return AgentResult(
                message=f"I encountered an error while processing your request: {str(e)}",
                tool_calls=[],
                suggestions=[]
            )

    async def run_chat_stream(self, message: str, session_id: str | None):
        """
        Execute a chat turn and stream the response.

        Args:
            message: User message to process
            session_id: Session identifier for conversation isolation

        Yields:
            Dict chunks with type and content for streaming
        """
        # Ensure agent is initialized
        if not self._initialized:
            await self.initialize()

        # Use a default session if none provided
        if session_id is None:
            session_id = "default"

        # Get session-specific memory
        memory = self.get_or_create_memory(session_id)

        # Create agent executor with session-specific memory
        agent_executor = self.create_agent_executor(memory)

        logger.info(f"Processing streaming message for session: {session_id}")

        try:
            # Stream the agent response
            response_text = ""
            tool_calls = []

            async for chunk in agent_executor.astream({"input": message}):
                # Handle different chunk types
                if "actions" in chunk:
                    # Tool execution started
                    for action in chunk["actions"]:
                        tool_name = action.tool
                        tool_input = action.tool_input

                        yield {
                            "type": "tool",
                            "status": "executing",
                            "tool": tool_name,
                            "arguments": tool_input,
                        }

                        tool_calls.append({
                            "tool": tool_name,
                            "arguments": tool_input
                        })

                elif "steps" in chunk:
                    # Tool execution completed
                    for step in chunk["steps"]:
                        # LangChain may return an AgentStep object or a tuple/list
                        action = getattr(step, "action", None)
                        observation = getattr(step, "observation", None)

                        if action is None and isinstance(step, (tuple, list)) and len(step) >= 2:
                            action, observation = step[0], step[1]

                        if action is None:
                            continue

                        yield {
                            "type": "tool",
                            "status": "completed",
                            "tool": action.tool,
                            "arguments": getattr(action, "tool_input", None),
                            "result": observation,
                        }

                        # Attach observation output to the most recent matching tool call
                        for existing in reversed(tool_calls):
                            if existing.get("tool") == action.tool and "output" not in existing:
                                existing["output"] = str(observation)[:200]
                                break
                        else:
                            tool_calls.append({
                                "tool": action.tool,
                                "input": getattr(action, "tool_input", None),
                                "output": str(observation)[:200]
                            })

                elif "output" in chunk:
                    # Final output
                    response_text = chunk["output"]

                    # Stream the response text token by token
                    words = response_text.split()
                    for i, word in enumerate(words):
                        yield {
                            "type": "token",
                            "message": word + (" " if i < len(words) - 1 else "")
                        }

            # Send completion event
            yield {
                "type": "complete",
                "message": response_text,
                "tool_calls": tool_calls
            }

            logger.info(f"Completed streaming for session {session_id}, used {len(tool_calls)} tools")

        except Exception as e:
            logger.error(f"Error in streaming chat: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"I encountered an error: {str(e)}"
            }
