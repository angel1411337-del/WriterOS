"""
LLM Client Wrapper with Function Calling Support

This module provides a wrapper around LangChain's ChatOpenAI that adds:
- Streaming with function calling support
- Tool call detection and parsing
- Consistent response format for both text and tool calls
- LCEL chain support for composability
- Pydantic structured output parsing
"""
import json
from typing import List, Dict, Any, Optional, AsyncGenerator, Union, Type
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
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

    def build_chain(
        self,
        prompt_template: Optional[ChatPromptTemplate] = None,
        response_format: Optional[Type[BaseModel]] = None,
        preprocessor: Optional[callable] = None
    ):
        """
        Build an LCEL chain with optional preprocessing and structured output.

        This enables composable chains like:
        preprocessor | prompt | llm | parser

        Args:
            prompt_template: ChatPromptTemplate for formatting messages
            response_format: Pydantic model for structured output parsing
            preprocessor: Optional callable for preprocessing input (e.g., RAG retrieval)

        Returns:
            Runnable LCEL chain

        Example:
            >>> prompt = ChatPromptTemplate.from_messages([
            ...     ("system", "You are a helpful assistant"),
            ...     ("user", "{query}")
            ... ])
            >>> chain = client.build_chain(prompt, response_format=MyPydanticModel)
            >>> result = await chain.ainvoke({"query": "Tell me about..."})
        """
        # Start with the base model
        chain = self.client

        # Add parser if structured output is requested
        if response_format:
            parser = PydanticOutputParser(pydantic_object=response_format)

            # If we have a prompt template, inject format instructions
            if prompt_template:
                # Add format instructions to prompt variables
                chain = (
                    RunnablePassthrough.assign(
                        format_instructions=lambda _: parser.get_format_instructions()
                    )
                    | prompt_template
                    | self.client
                    | parser
                )
            else:
                chain = self.client | parser
        elif prompt_template:
            chain = prompt_template | self.client | StrOutputParser()
        else:
            chain = self.client | StrOutputParser()

        # Add preprocessor at the start if provided
        if preprocessor:
            chain = RunnableLambda(preprocessor) | chain

        logger.info(
            "lcel_chain_built",
            has_prompt=prompt_template is not None,
            has_parser=response_format is not None,
            has_preprocessor=preprocessor is not None
        )

        return chain

    async def chat_with_parser(
        self,
        messages: List[Dict[str, str]],
        response_format: Type[BaseModel]
    ) -> BaseModel:
        """
        Chat with automatic Pydantic parsing of the response.

        This is a convenience method for getting structured outputs without
        building a full LCEL chain.

        Args:
            messages: List of message dicts
            response_format: Pydantic model class for parsing

        Returns:
            Parsed Pydantic model instance

        Example:
            >>> from pydantic import BaseModel
            >>> class TimelineExtraction(BaseModel):
            ...     events: List[str]
            ...     continuity_notes: str
            >>> result = await client.chat_with_parser(
            ...     messages=[{"role": "user", "content": "Extract timeline"}],
            ...     response_format=TimelineExtraction
            ... )
            >>> print(result.events)  # Automatically parsed!
        """
        parser = PydanticOutputParser(pydantic_object=response_format)

        # Convert to LangChain messages
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

        # Add format instructions to the last user message
        if lc_messages and isinstance(lc_messages[-1], HumanMessage):
            lc_messages[-1].content += f"\n\n{parser.get_format_instructions()}"

        # Build and invoke chain
        chain = self.client | parser
        result = await chain.ainvoke(lc_messages)

        logger.info(
            "structured_output_parsed",
            model_type=response_format.__name__,
            success=True
        )

        return result
