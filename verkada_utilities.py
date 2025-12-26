# Verkada Utilities
# This module provides utility functions for ProjectDecommission.
import os
from typing import Any, Callable, Dict, List, Optional, Union


def get_env_var(key: str, default: Optional[str] = None) -> str:
    """Safely gets a required environment variable with optional default."""
    value = os.environ.get(key, default)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


def sanitize_list(
    base_list: List[Dict[str, Any]], unsanitized_list: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Sanitizes the camera list by removing any cameras that are not associated with an intercom."""
    sanitized_list = []
    for item in unsanitized_list:
        if item["serial_number"] not in [
            device["serial_number"] for device in base_list
        ]:
            sanitized_list.append(item)
    return sanitized_list
