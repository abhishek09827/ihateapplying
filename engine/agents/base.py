import os
import re
import json
import time
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
from engine.config import (
    OPENROUTER_API_KEY,
    GROQ_API_KEY,
    LLM_PROVIDER,
    OPENROUTER_FREE_MODELS,
    GROQ_PRIMARY_MODEL,
    GROQ_FALLBACK_MODEL
)

logger = logging.getLogger("BaseAgent")

def clean_json_content(raw_str: str) -> Dict[str, Any]:
    """Extracts valid JSON from raw LLM responses wrapped in markdown codeblocks."""
    if not raw_str:
        return {}

    cleaned = raw_str.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Fallback: search for first '{' and matching '}'
    match = re.search(r'(\{[\s\S]*\})', cleaned)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    return {}

class BaseAgent:
    """
    Base autonomous agent providing resilient JSON generation with automated
    retries, rate-limit backoff, and instant failover between OpenRouter and Groq.
    """

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.provider = self._resolve_provider()
        self.client = self._init_client()

    def _resolve_provider(self) -> str:
        """Determines active LLM provider based on config and available keys."""
        if LLM_PROVIDER in ("OPENROUTER", "GROQ"):
            return LLM_PROVIDER
        if OPENROUTER_API_KEY:
            return "OPENROUTER"
        elif GROQ_API_KEY:
            return "GROQ"
        else:
            logger.warning("No LLM API key found. Set either GROQ_API_KEY or OPENROUTER_API_KEY in .env")
            return "GROQ"

    def _init_client(self) -> Optional[OpenAI]:
        """Initializes OpenAI client configured for the active provider."""
        if self.provider == "OPENROUTER" and OPENROUTER_API_KEY:
            return OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
                timeout=18.0,
                max_retries=1,
                default_headers={
                    "HTTP-Referer": "https://github.com/ai-outreach-engine",
                    "X-Title": "AI Outreach Engine"
                }
            )
        elif GROQ_API_KEY:
            return OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=GROQ_API_KEY,
                timeout=18.0,
                max_retries=1
            )
        return None

    def _get_model_hierarchy(self) -> List[str]:
        """Returns ordered list of models for the active provider."""
        if self.provider == "OPENROUTER":
            return OPENROUTER_FREE_MODELS
        return [GROQ_PRIMARY_MODEL, GROQ_FALLBACK_MODEL]

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 2,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Executes an LLM chat completion expecting a JSON response,
        with automated retries and instant 429 quota failover to Groq.
        """
        if not self.client:
            self.provider = self._resolve_provider()
            self.client = self._init_client()

        if not self.client:
            raise ValueError("Cannot call LLM: No valid API key configured. Run 'python setup.py' to add a key.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        consecutive_connection_errors = 0
        models_to_try = self._get_model_hierarchy()

        for model in models_to_try:
            delay = 1.0
            for attempt in range(max_retries):
                try:
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "timeout": 18.0
                    }
                    try:
                        kwargs["response_format"] = {"type": "json_object"}
                        response = self.client.chat.completions.create(**kwargs)
                    except Exception as inner_e:
                        inner_str = str(inner_e).lower()
                        if "response_format" in inner_str or "json_object" in inner_str:
                            kwargs.pop("response_format", None)
                            response = self.client.chat.completions.create(**kwargs)
                        else:
                            raise inner_e

                    raw_content = response.choices[0].message.content
                    return clean_json_content(raw_content)

                except Exception as e:
                    err_str = str(e)
                    cause = getattr(e, "__cause__", None)
                    cause_str = f" [cause: {cause}]" if cause else ""
                    logger.warning(
                        f"[{self.name}] Model {self.provider}:{model} (attempt {attempt + 1}) failed: {err_str[:120]}{cause_str}"
                    )

                    # Connection error detection
                    if "connection error" in err_str.lower() or "connect" in err_str.lower():
                        consecutive_connection_errors += 1
                        if consecutive_connection_errors >= 2 and GROQ_API_KEY:
                            logger.info(f"[{self.name}] OpenRouter connection dropped. Fast failover to Groq...")
                            break
                    else:
                        consecutive_connection_errors = 0

                    # 429 Account Quota detection
                    if "429" in err_str or "rate_limit" in err_str.lower():
                        if any(k in err_str.lower() for k in ("free-models-per-day", "credits", "quota", "exceeded")):
                            logger.warning(f"[{self.name}] OpenRouter account daily limit hit. Fast failover to Groq.")
                            consecutive_connection_errors = 99
                            break
                        time.sleep(delay)
                        delay *= 2
                    elif attempt == max_retries - 1:
                        break
                    else:
                        time.sleep(1.0)

            if consecutive_connection_errors >= 2 and GROQ_API_KEY:
                break

        # Fast fallback to Groq if OpenRouter models fail
        if GROQ_API_KEY:
            logger.info(f"[{self.name}] Executing fallback to Groq ({GROQ_PRIMARY_MODEL})...")
            try:
                groq_client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=GROQ_API_KEY,
                    timeout=18.0,
                    max_retries=1
                )
                resp = groq_client.chat.completions.create(
                    model=GROQ_PRIMARY_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    timeout=18.0
                )
                return clean_json_content(resp.choices[0].message.content)
            except Exception as e:
                logger.error(f"[{self.name}] Groq fallback also failed: {e}")

        raise RuntimeError(f"[{self.name}] Failed to generate valid JSON across provider models.")
