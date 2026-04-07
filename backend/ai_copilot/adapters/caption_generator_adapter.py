"""CaptionGeneratorAdapter — calls LLM gateway to generate Instagram captions."""

from __future__ import annotations

from ai_copilot.application.content_pipeline.ports import CaptionGeneratorPort

_SYSTEM_PROMPT = """You are an expert Instagram content creator.
Generate an engaging, on-brand caption for the given campaign brief.
The caption should:
- Be 50-300 characters
- Include 3-5 relevant hashtags at the end
- Match the tone of the brief
- Be ready to post immediately

Respond with ONLY the caption text. No explanations."""


class CaptionGeneratorAdapter(CaptionGeneratorPort):
    """Wraps LLMGatewayPort to generate captions via the configured LLM provider."""

    def __init__(
        self,
        llm_gateway,
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ):
        self._gateway = llm_gateway
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._provider_base_url = provider_base_url

    async def generate(
        self,
        campaign_brief: str,
        media_refs: list[str],
        previous_feedback: str | None = None,
        attempt: int = 1,
    ) -> str:
        user_content = f"Campaign brief: {campaign_brief}"
        if media_refs:
            user_content += f"\nMedia: {', '.join(media_refs[:3])}"
        if previous_feedback:
            user_content += f"\n\nPrevious caption was rejected. Feedback: {previous_feedback}\nPlease revise accordingly."
        if attempt > 1:
            user_content += f"\n(Attempt {attempt} — make it fresh and different from before)"

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            response = await self._gateway.request_completion(
                messages=messages,
                provider=self._provider,
                model=self._model,
                api_key=self._api_key,
                provider_base_url=self._provider_base_url,
            )
            # Extract text from response
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
                return response.get("content", "").strip()
            return str(response).strip()
        except Exception as exc:
            raise RuntimeError(f"Caption generation failed: {exc}") from exc
