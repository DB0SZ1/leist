import json
from openai import AsyncOpenAI
from app.config import settings
import structlog
from typing import List, Dict, Any

logger = structlog.get_logger()

# We use OpenRouter, typically mapped to Claude Haiku or OpenAI for speed and cost
def get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY
    )

async def generate_cold_sequence(
    job_name: str,
    target_icp: str,
    value_proposition: str,
    num_steps: int = 3
) -> List[Dict[str, Any]]:
    """
    Calls the LLM to generate a personalized B2B cold email sequence.
    Returns a list of dicts: {"step": 1, "subject": "...", "body_html": "..."}
    """
    
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is missing. Cannot generate sequence.")

    client = get_llm_client()
    
    prompt = f"""
    You are an expert B2B copywriter. Write a {num_steps}-step cold email sequence.
    
    Context:
    - Target Audience/ICP: {target_icp} (Campaign Name: {job_name})
    - Value Proposition / Goal: {value_proposition}
    
    Rules:
    1. Keep emails short and punchy. No generic marketing jargon.
    2. Use HTML formatting for the body (e.g., <p>, <br>).
    3. Use merge tags explicitly like: {{first_name}}, {{company}}, {{title}}.
    4. Provide the exact output as a JSON array of objects.

    Output format:
    [
      {{
        "step": 1,
        "subject": "Quick question about {{company}}",
        "body_html": "<p>Hi {{first_name}},</p><p>...</p>"
      }},
      ...
    ]
    """

    try:
        response = await client.chat.completions.create(
            model="anthropic/claude-3-haiku",
            messages=[
                {"role": "system", "content": "You output strictly raw JSON without markdown codeblocks."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}, # Some models support this on OpenRouter
            max_tokens=1500
        )
        
        content = response.choices[0].message.content.strip()
        
        # Ensure we just get JSON if the model appended markdown around it
        if content.startswith("```json"):
            content = content.replace("```json", "", 1)
        if content.endswith("```"):
            # Use rsplit to only remove the last occurrence
            content = content.rsplit("```", 1)[0]
            
        sequence = json.loads(content)
        
        # If the LLM returns an object wrapping an array, unwrap it
        if isinstance(sequence, dict):
            for k, v in sequence.items():
                if isinstance(v, list):
                    sequence = v
                    break
                    
        return sequence
    except Exception as e:
        logger.error("ai_generator_error", error=str(e))
        raise e
