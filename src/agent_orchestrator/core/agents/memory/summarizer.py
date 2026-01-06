"""Memory summarization for context compression."""

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agent_orchestrator.infrastructure.llm.client import LLMClient, LLMMessage

logger = structlog.get_logger(__name__)


class SummarizationConfig(BaseModel):
    """Configuration for memory summarization."""

    max_messages_before_summary: int = Field(
        default=20,
        description="Number of messages before triggering summarization.",
    )
    preserve_recent: int = Field(
        default=5,
        description="Number of recent messages to preserve (not summarize).",
    )
    summary_max_tokens: int = Field(
        default=500,
        description="Maximum tokens for the summary.",
    )
    model: str | None = Field(
        default=None,
        description="Model to use for summarization (None uses default).",
    )


class Message(BaseModel):
    """A conversation message."""

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class MemorySummarizer:
    """Summarizes old conversation messages to save context window space."""

    SUMMARY_PROMPT = """You are a conversation summarizer. Your task is to create a concise summary of the conversation history that:

1. Preserves key information and context
2. Maintains important user preferences and instructions
3. Keeps track of any important decisions or agreements made
4. Notes any relevant facts or data that may be needed later

Conversation to summarize:
{conversation}

Provide a summary in 2-3 paragraphs that captures the essential context. Focus on information that would be helpful for continuing the conversation."""

    def __init__(
        self,
        llm_client: "LLMClient",
        config: SummarizationConfig | None = None,
    ) -> None:
        """Initialize the summarizer.

        Args:
            llm_client: LLM client for generating summaries.
            config: Summarization configuration.
        """
        self._llm = llm_client
        self._config = config or SummarizationConfig()

    def should_summarize(self, messages: list[Message]) -> bool:
        """Check if messages should be summarized.

        Args:
            messages: List of conversation messages.

        Returns:
            True if summarization is recommended.
        """
        # Don't summarize if below threshold
        if len(messages) <= self._config.max_messages_before_summary:
            return False

        # Don't summarize if most messages are already summaries
        summary_count = sum(
            1 for m in messages if m.role == "system" and "[Summary]" in m.content
        )
        if summary_count > len(messages) // 2:
            return False

        return True

    async def summarize(
        self,
        messages: list[Message],
    ) -> tuple[Message, list[Message]]:
        """Summarize older messages into a single summary message.

        Args:
            messages: List of conversation messages.

        Returns:
            Tuple of (summary_message, recent_messages_to_keep).
        """
        preserve_count = self._config.preserve_recent

        # Split messages
        if len(messages) <= preserve_count:
            # Nothing to summarize
            return messages[0], messages

        to_summarize = messages[:-preserve_count]
        to_keep = messages[-preserve_count:]

        # Format conversation for summarization
        conversation_text = self._format_conversation(to_summarize)

        # Generate summary
        summary_content = await self._generate_summary(conversation_text)

        # Create summary message
        summary_message = Message(
            role="system",
            content=f"[Summary of previous {len(to_summarize)} messages]\n{summary_content}",
        )

        logger.info(
            "Conversation summarized",
            original_count=len(to_summarize),
            preserved_count=len(to_keep),
            summary_length=len(summary_content),
        )

        return summary_message, to_keep

    def _format_conversation(self, messages: list[Message]) -> str:
        """Format messages into a readable conversation text.

        Args:
            messages: List of messages to format.

        Returns:
            Formatted conversation string.
        """
        lines = []

        for msg in messages:
            role = msg.role.capitalize()
            if msg.name:
                role = f"{role} ({msg.name})"

            # Skip tool results in summary (they're usually verbose)
            if msg.role == "tool":
                lines.append(f"{role}: [Tool result provided]")
            else:
                # Truncate very long messages
                content = msg.content
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(f"{role}: {content}")

        return "\n".join(lines)

    async def _generate_summary(self, conversation: str) -> str:
        """Generate a summary using the LLM.

        Args:
            conversation: Formatted conversation text.

        Returns:
            Summary text.
        """
        from agent_orchestrator.infrastructure.llm.client import LLMMessage

        prompt = self.SUMMARY_PROMPT.format(conversation=conversation)

        response = await self._llm.complete(
            messages=[LLMMessage(role="user", content=prompt)],
            max_tokens=self._config.summary_max_tokens,
            model=self._config.model,
        )

        return response.content

    async def summarize_for_storage(
        self,
        messages: list[Message],
        include_tool_calls: bool = False,
    ) -> str:
        """Create a summary suitable for long-term storage.

        This creates a more detailed summary for storing in long-term memory,
        capturing important facts and context that may be useful later.

        Args:
            messages: List of conversation messages.
            include_tool_calls: Whether to include tool call details.

        Returns:
            Summary text for storage.
        """
        from agent_orchestrator.infrastructure.llm.client import LLMMessage

        storage_prompt = """Analyze this conversation and extract key information for long-term memory:

{conversation}

Create a structured summary with:
1. **Main Topics**: What was discussed
2. **Key Facts**: Important information mentioned (names, dates, preferences, etc.)
3. **Decisions Made**: Any agreements or decisions
4. **User Preferences**: Any preferences or instructions given by the user
5. **Context**: Any context that would be helpful for future conversations

Be concise but thorough. Format as bullet points where appropriate."""

        conversation_text = self._format_conversation(messages)

        if include_tool_calls:
            # Add tool call details
            tool_calls = [m for m in messages if m.role == "tool"]
            if tool_calls:
                conversation_text += "\n\nTool interactions:\n"
                for tc in tool_calls[:5]:  # Limit to 5 tool calls
                    conversation_text += f"- {tc.name}: {tc.content[:200]}...\n"

        prompt = storage_prompt.format(conversation=conversation_text)

        response = await self._llm.complete(
            messages=[LLMMessage(role="user", content=prompt)],
            max_tokens=800,  # More detailed for storage
            model=self._config.model,
        )

        return response.content
