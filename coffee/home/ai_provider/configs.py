from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class OllamaConfig(BaseModel):
    host: str = Field(description="Ollama Server Host (http://localhost:11434)",
                      json_schema_extra={"admin_visible": False})
    verify_ssl: bool = Field(default=True, json_schema_extra={"admin_visible": True})
    auth_token: Optional[str] = Field(default=None, repr=False, json_schema_extra={"admin_visible": False})
    default_model: str = Field(default="phi4:latest", json_schema_extra={"admin_visible": True})
    model_names: List[str] = Field(default_factory=lambda: ["phi4:latest"], json_schema_extra={"admin_visible": False})
    request_timeout: int = Field(default=60, ge=1, le=600, json_schema_extra={"admin_visible": True})
    temperature: float = Field(default=0.8, ge=0.0, le=2.0, json_schema_extra={"admin_visible": True})
    top_p: float = Field(default=0.1, ge=0.0, le=1.0, json_schema_extra={"admin_visible": True})

    @classmethod
    @field_validator("model_names", mode="before")
    def split_model_names(cls, v):
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v

    class Config:
        from_attributes = True

    @staticmethod
    def _normalize_host(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        u = url.strip()
        if not u.startswith(("http://", "https://")):
            return f"http://{u}"
        return u

    @classmethod
    def from_provider(cls, provider: "Provider"):
        cfg: Dict[str, Any] = {}
        cfg_json: Dict[str, Any] = (provider.config or {}).copy()

        # 1) Mapping aus provider.config (nutzt evtl. „alias“-Keys)
        #    Erlaubt alternative Schlüssel in der JSON: "timeout" statt "request_timeout", "verify" statt "verify_ssl" etc.
        alias_map = {
            "host": "host",
            "endpoint": "host",
            "verify": "verify_ssl",
            "verify_ssl": "verify_ssl",
            "auth_token": "auth_token",
            "api_key": "auth_token",
            "default_model": "default_model",
            "model_names": "model_names",
            "timeout": "request_timeout",
            "request_timeout": "request_timeout",
            "temperature": "temperature",
            "top_p": "top_p",
        }
        for key, value in cfg_json.items():
            target = alias_map.get(key)
            if target is None:
                continue
            cfg[target] = value

        # 2) Provider-Felder (überschreiben JSON, falls gesetzt)
        if provider.endpoint:
            cfg["host"] = provider.endpoint
        if provider.api_key:
            cfg["auth_token"] = provider.api_key

        # Host normalisieren (Schema ergänzen, falls fehlt)
        if "host" in cfg:
            cfg["host"] = cls._normalize_host(cfg["host"])

        return cls.model_validate(cfg)

        # # 4) Validierung durch Pydantic
        # try:
        #     return cls.model_validate(cfg)
        # except ValidationError as e:
        #     # Zusatzinfos für Debugging
        #     raise ValidationError(
        #         e.errors(),
        #         cls,
        #     ) from e

class AzureAIConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

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

    # Modelle
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

    # -------- Factory aus Provider --------
    @classmethod
    def from_provider(cls, provider: "Provider") -> "AzureAIConfig":
        """
        Erzeugt eine AzureAIConfig aus dem Provider-ORM-Objekt.
        Priorität:
          1) provider.endpoint / provider.api_key (Model-Felder)
          2) provider.config (JSON) mit Alias-Mapping
          3) Defaults aus diesem Schema
        """
        cfg: Dict[str, Any] = {}
        cfg_json: Dict[str, Any] = (provider.config or {}).copy()

        # Aliase erlauben bequeme Keys in JSON-Config
        alias_map = {
            # Verbindung
            "endpoint": "endpoint",
            "base_url": "endpoint",

            "api_key": "api_key",
            "key": "api_key",

            "api_version": "api_version",
            "version": "api_version",

            # Modelle
            "default_model": "default_model",
            "model_names": "model_names",
            "models": "model_names",

            # Inferenz
            "max_tokens": "max_tokens",
            "temperature": "temperature",
            "top_p": "top_p",
            "presence_penalty": "presence_penalty",
            "frequency_penalty": "frequency_penalty",
        }

        for key, value in cfg_json.items():
            target = alias_map.get(key)
            if target is None:
                continue
            cfg[target] = value

        # Provider-Felder überschreiben JSON (Single Source of Truth)
        if getattr(provider, "endpoint", None):
            cfg["endpoint"] = provider.endpoint
        if getattr(provider, "api_key", None):
            cfg["api_key"] = provider.api_key

        # Falls nur default_model gesetzt ist, aber keine Liste → Liste ergänzen
        if "default_model" in cfg and "model_names" not in cfg:
            cfg["model_names"] = [cfg["default_model"]]

        return cls.model_validate(cfg)


class AzureOpenAIConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

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
        description="Azure OpenAI API Version",
        json_schema_extra={"admin_visible": True},
    )

    # Deployments / Modelle
    default_model: str = Field(
        default="gpt-4o-mini", json_schema_extra={"admin_visible": True}
    )
    model_names: List[str] = Field(
        default_factory=lambda: ["gpt-4o-mini"], json_schema_extra={"admin_visible": False}
    )

    # Inferenz-Parameter
    max_tokens: int = Field(default=2000, ge=1, json_schema_extra={"admin_visible": True})
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, json_schema_extra={"admin_visible": True})
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, json_schema_extra={"admin_visible": True})

    # Request-Timeout (für SDK-Calls)
    request_timeout: int = Field(default=30, ge=1, le=600, json_schema_extra={"admin_visible": True})

    # ---------- Validatoren ----------
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
            u = f"https://{u}"
        return u

    # ---------- Factory aus Provider ----------
    @classmethod
    def from_provider(cls, provider: "Provider") -> "AzureOpenAIConfig":
        """
        Baut eine Config aus dem Provider-ORM-Objekt.
        Priorität:
          1) provider.endpoint / provider.api_key
          2) provider.config (JSON) mit Alias-Mapping
          3) Defaults dieses Schemas
        """
        cfg: Dict[str, Any] = {}
        cfg_json: Dict[str, Any] = (provider.config or {}).copy()

        alias_map = {
            # Verbindung
            "endpoint": "endpoint",
            "base_url": "endpoint",
            "api_key": "api_key",
            "key": "api_key",
            "api_version": "api_version",
            "version": "api_version",

            # Deployments/Modelle
            "default_model": "default_model",
            "deployment": "default_model",
            "model_names": "model_names",
            "deployments": "model_names",

            # Inferenz
            "max_tokens": "max_tokens",
            "temperature": "temperature",
            "top_p": "top_p",

            # Timeout
            "timeout": "request_timeout",
            "request_timeout": "request_timeout",
        }

        for k, v in cfg_json.items():
            t = alias_map.get(k)
            if t:
                cfg[t] = v

        if getattr(provider, "endpoint", None):
            cfg["endpoint"] = provider.endpoint
        if getattr(provider, "api_key", None):
            cfg["api_key"] = provider.api_key

        if "default_model" in cfg and "model_names" not in cfg:
            cfg["model_names"] = [cfg["default_model"]]

        return cls.model_validate(cfg)
