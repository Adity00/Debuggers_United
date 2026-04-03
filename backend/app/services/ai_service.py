"""
OpenAI wrapper and service catalog provider.
"""
import openai
from openai import AsyncOpenAI
from app.config import settings

SERVICE_CATALOG = {
    "code_review": {
        "id": "code_review",
        "name": "Code Reviewer",
        "description": "Senior engineer reviews your code for bugs, security, and performance.",
        "price_algo": 0.5,
        "price_microalgo": 500_000,
        "example_prompt": "Review this Python function for bugs and improvements: ...",
        "system_prompt": (
            "You are a senior software engineer with 15 years of experience. "
            "Conduct a thorough code review analyzing: correctness, edge cases, "
            "security vulnerabilities, performance bottlenecks, and style. "
            "Structure your response with sections: 🐛 Bugs, 🔒 Security, "
            "⚡ Performance, ✅ What's Good, 📝 Suggestions. Be specific and actionable."
        )
    },
    "essay_writer": {
        "id": "essay_writer",
        "name": "Essay Writer",
        "description": "Award-winning writer crafts compelling essays on any topic.",
        "price_algo": 1.0,
        "price_microalgo": 1_000_000,
        "example_prompt": "Write a 300-word persuasive essay on why open source software matters.",
        "system_prompt": (
            "You are an award-winning essayist and editor published in major journals. "
            "Write compelling, well-structured essays with a strong thesis, supporting "
            "arguments, and memorable conclusion. Match tone (formal/casual) to the request. "
            "Always include: an engaging hook, clear structure, and a call to action."
        )
    },
    "data_analyst": {
        "id": "data_analyst",
        "name": "Data Analyst",
        "description": "Senior data scientist analyzes your data and surfaces key insights.",
        "price_algo": 2.0,
        "price_microalgo": 2_000_000,
        "example_prompt": "Analyze: monthly sales data showing 20% drop in Q3 vs Q2 for a retail brand.",
        "system_prompt": (
            "You are a senior data scientist at a top analytics firm. "
            "When given data or a business problem: identify key trends, surface anomalies, "
            "suggest statistical tests if appropriate, and recommend visualization types. "
            "Structure your response: 📊 Key Findings, 🔍 Root Cause Hypotheses, "
            "📈 Recommended Visualizations, 🎯 Next Steps. Be quantitative and specific."
        )
    },
    "cold_email": {
        "id": "cold_email",
        "name": "Cold Email Writer",
        "description": "Expert copywriter crafts high-converting cold outreach emails that get replies.",
        "price_algo": 0.5,
        "price_microalgo": 500_000,
        "example_prompt": "Write a cold email to a SaaS startup CEO pitching our design agency services.",
        "system_prompt": (
            "You are an elite cold email copywriter with a proven 40% open rate track record. "
            "Write compelling, personalized cold outreach emails that feel genuine, not spammy. "
            "Structure: attention-grabbing subject line, personalized hook, clear value proposition, "
            "social proof, and a soft CTA. Keep it under 150 words. Avoid salesy language. "
            "Always provide 3 variations: formal, casual, and ultra-short."
        )
    },
    "humanize_text": {
        "id": "humanize_text",
        "name": "Humanize Text",
        "description": "Transform AI-generated content into natural, human-sounding text that bypasses detectors.",
        "price_algo": 0.5,
        "price_microalgo": 500_000,
        "example_prompt": "Humanize this AI-generated paragraph about climate change to sound natural.",
        "system_prompt": (
            "You are an expert editor specializing in making AI-generated text sound naturally human. "
            "Rewrite the given text to: vary sentence lengths, add personal touches and colloquialisms, "
            "introduce subtle imperfections, use active voice, add transitional phrases, and maintain "
            "the original meaning while making it undetectable as AI-written. "
            "Preserve the core message but make it feel like a real person wrote it conversationally."
        )
    }
}

def get_services_list() -> list[dict]:
    """
    Returns array containing all services available in the catalog.
    """
    return list(SERVICE_CATALOG.values())

async def get_ai_response(service_id: str, user_prompt: str) -> tuple[str, int]:
    """
    Proxies query to OpenAI with the mapped system prompt.
    Returns the message text and token consumption.
    """
    if service_id not in SERVICE_CATALOG:
        raise ValueError("Invalid service_id provided for AI inference.")
        
    system_prompt = SERVICE_CATALOG[service_id]["system_prompt"]
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=800,
            temperature=0.7
        )
        
        reply_text = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        
        return reply_text, tokens_used
        
    except openai.RateLimitError as e:
        raise RuntimeError("OpenAI rate limit exceeded. Please try again later.") from e
    except openai.APIError as e:
        raise RuntimeError(f"OpenAI API error occurred: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error interfacing with OpenAI: {e}") from e


async def get_ai_response_with_context(service_id: str, messages: list[dict]) -> tuple[str, int]:
    """
    Multi-turn conversation support.
    Takes a list of {role, content} messages and returns AI response with full context.
    """
    if service_id not in SERVICE_CATALOG:
        raise ValueError("Invalid service_id provided for AI inference.")
        
    system_prompt = SERVICE_CATALOG[service_id]["system_prompt"]
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    # Build full message array with system prompt + conversation history
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages,
            max_tokens=1500,
            temperature=0.7
        )
        
        reply_text = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        
        return reply_text, tokens_used
        
    except openai.RateLimitError as e:
        raise RuntimeError("OpenAI rate limit exceeded. Please try again later.") from e
    except openai.APIError as e:
        raise RuntimeError(f"OpenAI API error occurred: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error interfacing with OpenAI: {e}") from e
