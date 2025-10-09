"""
Minimal LLM Wrapper for Contextual Retrieval

Stripped-down version with only OpenAI support for generating chunk context.
"""

from openai import AsyncOpenAI


class SimpleLLMService:
    """Minimal LLM service for contextual chunk enhancement."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model to use for context generation
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_chunk_context(
        self, document_content: str, chunk_content: str
    ) -> str:
        """
        Generate context for a chunk based on the full document.

        Args:
            document_content: Full document text
            chunk_content: The chunk text to generate context for

        Returns:
            Context string to prepend to the chunk
        """
        prompt = f"""<document>
{document_content}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_content}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )

        return response.choices[0].message.content or ""
