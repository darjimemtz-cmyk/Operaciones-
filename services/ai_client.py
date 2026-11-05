"""
AI Client service for interacting with Groq and Gemini APIs.
Implements deterministic fallback: Groq -> Gemini with strict 8-second timeout.
"""

import os
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

import groq
from google import genai


@dataclass
class AIResponse:
    """Standardized response from AI providers."""
    content: str
    provider: str
    latency_ms: int
    success: bool
    error: Optional[str] = None


class AIClient:
    """
    AI Client with dual-provider support and deterministic fallback.
    
    Fallback order: Groq (primary) -> Gemini (fallback)
    Strict timeout: 15 seconds per provider
    """
    
    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        timeout_seconds: int = 15
    ):
        """
        Initialize AI clients for Groq and Gemini.
        
        Args:
            groq_api_key: Groq API key (defaults to GROQ_API_KEY env var)
            gemini_api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            timeout_seconds: Request timeout in seconds (default 8)
        """
        self.timeout_seconds = timeout_seconds
        
        # Initialize Groq client
        self.groq_client = None
        groq_key = groq_api_key or os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                self.groq_client = groq.Groq(api_key=groq_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Groq client: {e}")
        
        # Initialize Gemini client
        self.gemini_client = None
        gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini client: {e}")
    
    def query(self, prompt: str, system_prompt: Optional[str] = None) -> AIResponse:
        """
        Query AI with deterministic fallback: Groq -> Gemini.
        
        Args:
            prompt: User prompt to send to the AI
            system_prompt: Optional system prompt for context
            
        Returns:
            AIResponse with content, provider used, latency, and success status
        """
        # Try Groq first (primary)
        if self.groq_client:
            response = self._query_groq(prompt, system_prompt)
            if response.success:
                return response
        
        # Fallback to Gemini
        if self.gemini_client:
            response = self._query_gemini(prompt, system_prompt)
            if response.success:
                return response
        
        # Both failed
        return AIResponse(
            content="",
            provider="none",
            latency_ms=0,
            success=False,
            error="All AI providers unavailable or failed"
        )
    
    def _query_groq(self, prompt: str, system_prompt: Optional[str] = None) -> AIResponse:
        """Query Groq API with timeout."""
        start_time = time.time()
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Groq doesn't have native timeout, we implement it via threading
            import threading
            result = {"response": None, "error": None}
            
            def call_groq():
                try:
                    completion = self.groq_client.chat.completions.create(
                        model="qwen/qwen3.8-27b",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=2048
                    )
                    result["response"] = completion.choices[0].message.content
                except Exception as e:
                    result["error"] = str(e)
            
            thread = threading.Thread(target=call_groq)
            thread.start()
            thread.join(timeout=self.timeout_seconds)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if thread.is_alive():
                # Timeout occurred
                return AIResponse(
                    content="",
                    provider="groq",
                    latency_ms=latency_ms,
                    success=False,
                    error=f"Groq timeout after {self.timeout_seconds}s"
                )
            
            if result["error"]:
                return AIResponse(
                    content="",
                    provider="groq",
                    latency_ms=latency_ms,
                    success=False,
                    error=result["error"]
                )
            
            return AIResponse(
                content=result["response"],
                provider="groq",
                latency_ms=latency_ms,
                success=True
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return AIResponse(
                content="",
                provider="groq",
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    def _query_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> AIResponse:
        """Query Gemini API with timeout."""
        start_time = time.time()
        
        try:
            # Combine system prompt with user prompt for Gemini
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            import threading
            result = {"response": None, "error": None}
            
            def call_gemini():
                try:
                    response = self.gemini_client.models.generate_content(
                        model='gemini-3.5-flash-lite',
                        contents=full_prompt
                    )
                    result["response"] = response.text
                except Exception as e:
                    result["error"] = str(e)
            
            thread = threading.Thread(target=call_gemini)
            thread.start()
            thread.join(timeout=self.timeout_seconds)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if thread.is_alive():
                # Timeout occurred
                return AIResponse(
                    content="",
                    provider="gemini",
                    latency_ms=latency_ms,
                    success=False,
                    error=f"Gemini timeout after {self.timeout_seconds}s"
                )
            
            if result["error"]:
                return AIResponse(
                    content="",
                    provider="gemini",
                    latency_ms=latency_ms,
                    success=False,
                    error=result["error"]
                )
            
            return AIResponse(
                content=result["response"],
                provider="gemini",
                latency_ms=latency_ms,
                success=True
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return AIResponse(
                content="",
                provider="gemini",
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    def is_available(self) -> bool:
        """Check if at least one provider is configured."""
        return self.groq_client is not None or self.gemini_client is not None
    
    def get_available_providers(self) -> Dict[str, bool]:
        """Get status of each provider."""
        return {
            "groq": self.groq_client is not None,
            "gemini": self.gemini_client is not None
        }