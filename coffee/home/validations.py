from typing import Dict, Mapping, Any

from pydantic import ValidationError

from coffee.home.registry import SCHEMA_REGISTRY


def validate_config_for_type(provider_type: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    if provider_type not in SCHEMA_REGISTRY:
        raise ValueError(f"Unbekannter Provider-Typ: {provider_type}")
    try:
        return SCHEMA_REGISTRY[provider_type][0](**(config or {})).model_dump()
    except ValidationError as ve:
        errs = "; ".join([f"{'/'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in ve.errors()])
        raise ValueError(errs)