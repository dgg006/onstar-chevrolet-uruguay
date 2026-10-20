"""Minimal diagnostics: never export account, signing key or vehicle data."""
from . import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = runtime.get("coordinator")
    client = runtime.get("client")
    return {
        "loaded": bool(runtime),
        "last_update_success": bool(coordinator and coordinator.last_update_success),
        "app_version": getattr(client, "app_version", None),
        "scan_interval": entry.data.get("scan_interval", 1800),
        "auto_refresh": entry.data.get("auto_refresh", True),
    }
