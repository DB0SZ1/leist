"""
AI Copilot Service
Analyzes email subject and body for spam triggers, aggressiveness, and readability.
Uses OpenRouter (e.g., meta-llama/llama-3-8b-instruct or similar fast model) to generate feedback.
"""
import os
import json
import httpx
import structlog

log = structlog.get_logger()

# Optional: Set this model based on what you want to use.
DEFAULT_MODEL = "meta-llama/llama-3-8b-instruct:free"

async def analyze_email_content(subject: str, body: str) -> dict:
    """
    Sends the email draft to an LLM via OpenRouter and asks for structured JSON analysis.
    If OPENROUTER_API_KEY is not set, returns a mock analysis for demonstration purposes.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing. Cannot perform AI email analysis.")
        
    prompt = f"""
    You are an expert cold email consultant and deliverability specialist.
    Analyze the following email for potential spam triggers, tone aggressiveness, and overall readability.
    
    Subject: {subject}
    Body:
    {body}
    
    Return your analysis as a strict JSON object with the following schema:
    {{
        "spam_score": <int from 0 to 100, where 100 means highly likely to go to spam>,
        "aggressiveness_score": <int from 0 to 100, where 100 means very aggressive/salesy>,
        "readability_score": <int from 0 to 100, where 100 means very easy to read>,
        "spam_triggers_found": [<list of specific words or phrases found that trigger spam filters>],
        "feedback": "<A concise 2-3 sentence paragraph providing overall advice to improve the email>"
    }}
    
    Do not include any formatting or text outside of the JSON object.
    """
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://listintel.com",
                    "X-Title": "List Intel Pre-Send Copilot"
                },
                json={
                    "model": DEFAULT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Clean up potential markdown formatting
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
            
    except Exception as e:
        log.error("AI Copilot request failed", error=str(e))
        return {
            "spam_score": 0,
            "aggressiveness_score": 0,
            "readability_score": 0,
            "spam_triggers_found": [],
            "feedback": f"Failed to analyze email due to an API error. Please try again later."
        }

