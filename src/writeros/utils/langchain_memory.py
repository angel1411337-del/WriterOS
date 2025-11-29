"""
LangChain Memory Integration for WriterOS

This module provides LangChain-compatible memory implementations that integrate
with WriterOS's existing Conversation and Message schema.
"""
from typing import List, Optional
from uuid import UUID
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    message_to_dict,
    messages_from_dict,
)
from sqlmodel import Session, select
from writeros.schema.session import Conversation, Message
from writeros.utils.db import engine
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class PostgresChatHistory(BaseChatMessageHistory):
    """
    LangChain-compatible chat history backed by PostgreSQL.

    Integrates with WriterOS's existing Conversation and Message tables,
    enabling LangChain memory features like ConversationBufferMemory while
    preserving all WriterOS-specific metadata (agent, context_used, etc.).

    Usage:
        >>> history = PostgresChatHistory(conversation_id=conv_id)
        >>> history.add_user_message("Hello!")
        >>> history.add_ai_message("Hi there!")
        >>> messages = history.messages  # Returns list of LangChain messages
    """

    def __init__(self, conversation_id: UUID, agent_name: Optional[str] = None):
        """
        Initialize chat history for a specific conversation.

        Args:
            conversation_id: UUID of the conversation
            agent_name: Optional agent name to tag AI messages with
        """
        self.conversation_id = conversation_id
        self.agent_name = agent_name
        logger.info(
            "postgres_chat_history_initialized",
            conversation_id=str(conversation_id),
            agent_name=agent_name
        )

    @property
    def messages(self) -> List[BaseMessage]:
        """
        Retrieve all messages from the database as LangChain messages.

        Returns:
            List of LangChain BaseMessage objects (HumanMessage, AIMessage, SystemMessage)
        """
        with Session(engine) as session:
            # Get all messages for this conversation, ordered by creation time
            statement = (
                select(Message)
                .where(Message.conversation_id == self.conversation_id)
                .order_by(Message.created_at)
            )
            db_messages = session.exec(statement).all()

            # Convert to LangChain messages
            lc_messages = []
            for msg in db_messages:
                lc_messages.append(self._db_message_to_langchain(msg))

            logger.info(
                "messages_retrieved",
                conversation_id=str(self.conversation_id),
                count=len(lc_messages)
            )

            return lc_messages

    def add_message(self, message: BaseMessage) -> None:
        """
        Add a LangChain message to the database.

        Args:
            message: LangChain BaseMessage to store
        """
        with Session(engine) as session:
            # Determine role from message type
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            elif isinstance(message, SystemMessage):
                role = "system"
            else:
                role = "unknown"

            # Create database message
            db_message = Message(
                conversation_id=self.conversation_id,
                role=role,
                content=message.content,
                agent=self.agent_name if role == "assistant" else None,
                context_used={}  # Can be populated with RAG context later
            )

            session.add(db_message)
            session.commit()

            logger.info(
                "message_added",
                conversation_id=str(self.conversation_id),
                role=role,
                agent=self.agent_name
            )

    def add_user_message(self, message: str) -> None:
        """
        Convenience method to add a user message.

        Args:
            message: User message content
        """
        self.add_message(HumanMessage(content=message))

    def add_ai_message(self, message: str) -> None:
        """
        Convenience method to add an AI message.

        Args:
            message: AI message content
        """
        self.add_message(AIMessage(content=message))

    def clear(self) -> None:
        """
        Delete all messages from this conversation.

        WARNING: This is destructive and cannot be undone.
        """
        with Session(engine) as session:
            statement = select(Message).where(
                Message.conversation_id == self.conversation_id
            )
            messages = session.exec(statement).all()

            for msg in messages:
                session.delete(msg)

            session.commit()

            logger.warning(
                "conversation_cleared",
                conversation_id=str(self.conversation_id),
                messages_deleted=len(messages)
            )

    def _db_message_to_langchain(self, db_message: Message) -> BaseMessage:
        """
        Convert a database Message to a LangChain BaseMessage.

        Args:
            db_message: WriterOS Message model

        Returns:
            LangChain BaseMessage (HumanMessage, AIMessage, or SystemMessage)
        """
        if db_message.role == "user":
            return HumanMessage(content=db_message.content)
        elif db_message.role == "assistant":
            return AIMessage(content=db_message.content)
        elif db_message.role == "system":
            return SystemMessage(content=db_message.content)
        else:
            # Default to HumanMessage for unknown roles
            return HumanMessage(content=db_message.content)


def get_or_create_conversation(vault_id: UUID, title: str = "New Conversation") -> UUID:
    """
    Helper function to get or create a conversation for a vault.

    Args:
        vault_id: UUID of the vault
        title: Optional title for new conversation

    Returns:
        UUID of the conversation
    """
    with Session(engine) as session:
        # Try to find an existing conversation for this vault
        statement = (
            select(Conversation)
            .where(Conversation.vault_id == vault_id)
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        existing_conv = session.exec(statement).first()

        if existing_conv:
            logger.info(
                "conversation_found",
                conversation_id=str(existing_conv.id),
                vault_id=str(vault_id)
            )
            return existing_conv.id
        else:
            # Create new conversation
            new_conv = Conversation(vault_id=vault_id, title=title)
            session.add(new_conv)
            session.commit()
            session.refresh(new_conv)

            logger.info(
                "conversation_created",
                conversation_id=str(new_conv.id),
                vault_id=str(vault_id)
            )
            return new_conv.id
