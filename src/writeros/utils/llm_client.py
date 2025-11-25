"""
LLM Client Wrapper with Function Calling Support

This module provides a wrapper around LangChain's ChatOpenAI that adds:
- Streaming with function calling support
- Tool call detection and parsing
- Consistent response format for both text and tool calls
"""
import json
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Wrapper around LangChain's ChatOpenAI with function calling support.
    """

    def __init__(self, model_name: str = "gpt-5.1", temperature: float = 0.7, api_key: str = None):
        self.model_name = model_name
        self.client = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=api_key
        )
        logger.info("llm_client_initialized", model=model_name)

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """
        Stream chat completion with optional function calling support.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of OpenAI function calling tool schemas

        Yields:
            Either:
            - str: Text chunks from the response
            - dict: Tool call information with structure:
                {
                    "type": "tool_call",
                    "id": "call_123",
                    "name": "tool_name",
                    "arguments": {...}
                }
        """
        # Convert dict messages to LangChain message objects
        lc_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "tool":
                # Tool result message
                lc_messages.append(ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", "")
                ))

        # Bind tools if provided
        if tools:
            # Convert OpenAI tool format to LangChain format
            lc_tools = self._convert_tools_to_langchain(tools)
            client = self.client.bind_tools(lc_tools)
        else:
            client = self.client

        # Stream the response
        try:
            async for chunk in client.astream(lc_messages):
                # Check if chunk contains tool calls
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    for tool_call in chunk.tool_calls:
                        yield {
                            "type": "tool_call",
                            "id": tool_call.get("id", ""),
                            "name": tool_call.get("name", ""),
                            "arguments": tool_call.get("args", {})
                        }
                # Regular text content
                elif hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error("llm_stream_failed", error=str(e))
            raise

    def _convert_tools_to_langchain(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert OpenAI function calling format to LangChain tool format.

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "...",
                "parameters": {...}
            }
        }

        LangChain format:
        {
            "name": "tool_name",
            "description": "...",
            "parameters": {...}
        }
        """
        lc_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                lc_tools.append({
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "parameters": func.get("parameters")
                })
            else:
                # Already in LangChain format
                lc_tools.append(tool)

        return lc_tools

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Non-streaming chat completion.

        Args:
            messages: List of message dicts
            tools: Optional tool schemas

        Returns:
            Complete response text
        """
        response = ""
        async for chunk in self.stream_chat(messages, tools):
            if isinstance(chunk, str):
                response += chunk
        return response

    def with_structured_output(self, schema):
        """
        Returns the underlying LangChain client with structured output binding.
        This is used by agents that need structured responses (e.g., ProfilerAgent).

        Args:
            schema: Pydantic schema for structured output

        Returns:
            LangChain client with structured output binding
        """
        return self.client.with_structured_output(schema)
