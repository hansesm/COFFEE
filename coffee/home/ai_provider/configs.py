from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class OllamaConfig(BaseModel):
    host: str = Field(description="Ollama Server Host (http://localhost:11434)",
                      json_schema_extra={"admin_visible": False})
    verify_ssl: bool = Field(default=True, json_schema_extra={"admin_visible": True})
    auth_token: Optional[str] = Field(default=None, repr=False, json_schema_extra={"admin_visible": False})
    default_model: str = Field(default="phi4:latest", json_schema_extra={"admin_visible": True})
    request_timeout: int = Field(default=60, ge=1, le=600, json_schema_extra={"admin_visible": True})

    model_config = ConfigDict(extra='forbid', from_attributes=True)

    @classmethod
    @field_validator("model_names", mode="before")
    def split_model_names(cls, v):
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v

    @classmethod
    def from_provider(cls, provider: "Provider"):
        data = dict(provider.config or {})

        if provider.endpoint:
            data["host"] = provider.endpoint
        if provider.api_key:
            data["auth_token"] = provider.api_key

        return cls.model_validate(data)

class AzureAIConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)

    endpoint: str = Field(
        description="Azure AI Inference Endpoint (z. B. https://<name>.inference.azure.com)",
        json_schema_extra={"admin_visible": False},
    )
    api_key: Optional[str] = Field(
        default=None,
        repr=False,
        json_schema_extra={"admin_visible": False},
    )
    api_version: str = Field(
        default="2024-05-01-preview",
        description="Azure AI API Version",
        json_schema_extra={"admin_visible": True},
    )

    deployment: str = Field(
        default="Phi-4",
        json_schema_extra={"admin_visible": True},
    )
    default_model: str = Field(
        default="Phi-4",
        json_schema_extra={"admin_visible": True},
    )
    model_names: List[str] = Field(
        default_factory=lambda: ["Phi-4"],
        json_schema_extra={"admin_visible": False},
    )

    # Inferenz-Parameter (entsprechen deinen getattr(settings, ...))
    max_tokens: int = Field(
        default=2048, ge=1, description="Maximale Anzahl generierter Tokens",
        json_schema_extra={"admin_visible": True},
    )
    temperature: float = Field(
        default=0.8, ge=0.0, le=2.0,
        json_schema_extra={"admin_visible": True},
    )
    top_p: float = Field(
        default=0.1, ge=0.0, le=1.0,
        json_schema_extra={"admin_visible": True},
    )
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0,
        json_schema_extra={"admin_visible": True},
    )
    frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0,
        json_schema_extra={"admin_visible": True},
    )

    # -------- Validatoren (Pydantic v2) --------
    @field_validator("model_names", mode="before")
    @classmethod
    def split_model_names(cls, v):
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v

    @field_validator("endpoint", mode="before")
    @classmethod
    def normalize_endpoint(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        u = str(v).strip()
        if not u.startswith(("http://", "https://")):
            # meist ist das Endpoint-API nur über HTTPS sinnvoll erreichbar
            u = f"https://{u}"
        return u

    @classmethod
    def from_provider(cls, provider: "Provider"):
        data = dict(provider.config or {})

        if provider.endpoint:
            data["endpoint"] = provider.endpoint
        if provider.api_key:
            data["api_key"] = provider.api_key

        return cls.model_validate(data)


class AzureOpenAIConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)

    # Verbindung
    endpoint: str = Field(
        description="Azure OpenAI Endpoint (https://<resource-name>.openai.azure.com oder https://<name>.openai.azure.com)",
        json_schema_extra={"admin_visible": False},
    )
    api_key: Optional[str] = Field(
        default=None, repr=False, json_schema_extra={"admin_visible": False}
    )
    api_version: str = Field(
        default="2024-12-01-preview",
        json_schema_extra={"admin_visible": True},
    )

    default_model: str = Field(
        default="gpt-4o-mini", json_schema_extra={"admin_visible": True}
    )

    max_retries: int = Field(default=2, ge=0, json_schema_extra={"admin_visible": True})
    request_timeout: int = Field(default=30, ge=1, le=600, json_schema_extra={"admin_visible": True})

    @field_validator("endpoint", mode="before")
    @classmethod
    def normalize_endpoint(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        u = str(v).strip()
        if not u.startswith(("http://", "https://")):
            u = f"https://{u}"
        return u

    @classmethod
    def from_provider(cls, provider: "Provider"):
        data = dict(provider.config or {})

        if provider.endpoint:
            data["endpoint"] = provider.endpoint
        if provider.api_key:
            data["api_key"] = provider.api_key

        return cls.model_validate(data)
