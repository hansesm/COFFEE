# app/validators.py
from pydantic import BaseModel, AnyHttpUrl, Field, ValidationError, HttpUrl
from typing import Optional, Dict, Any, Mapping, Union

# --- Azure AI (z.B. "Azure AI Inference") ---
class AzureAIConfig(BaseModel):
    api_version: str = Field(default="2024-05-01-preview")
    # optional gemeinsame Settings
    timeout: Optional[float] = Field(default=30.0, ge=0)
    headers: Optional[Dict[str, str]] = None
    verify_ssl: Optional[bool] = True

# --- Azure OpenAI ---
class AzureOpenAIConfig(BaseModel):
    api_version: str = Field(default="2024-12-01-preview")
    timeout: Optional[float] = Field(default=30.0, ge=0)
    headers: Optional[Dict[str, str]] = None
    verify_ssl: Optional[bool] = True

# --- Ollama ---
class OllamaConfig(BaseModel):
    timeout: Optional[float] = Field(default=30.0, ge=0)
    headers: Optional[Dict[str, str]] = None
    verify_ssl: Optional[bool] = True

SCHEMAS = {
    "azure_ai": AzureAIConfig,
    "azure_openai": AzureOpenAIConfig,
    "ollama": OllamaConfig,
}

def validate_config_for_type(provider_type: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    if provider_type not in SCHEMAS:
        raise ValueError(f"Unbekannter Provider-Typ: {provider_type}")
    try:
        return SCHEMAS[provider_type](**(config or {})).model_dump()
    except ValidationError as ve:
        # kompaktes Fehlermapping
        errs = "; ".join([f"{'/'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in ve.errors()])
        raise ValueError(errs)
