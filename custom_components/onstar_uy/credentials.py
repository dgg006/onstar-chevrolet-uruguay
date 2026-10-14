"""Read signing configuration only from the user's private installation."""
import json
import re
from pathlib import Path

from .client import OnStarClient, OnStarError
from .const import APP_CLIENT_ID, APP_DEFAULTS

KEY_FILENAME = "onstar_uy_private.json"


class SigningKeyError(OnStarError):
    """Missing or invalid private signing configuration."""


def load_signing_key(path, legacy_key=None):
    """An existing file takes priority; invalid files never silently fall back."""
    try:
        with Path(path).open("r", encoding="utf-8-sig") as handle:
            content = handle.read(16385)
    except FileNotFoundError:
        if isinstance(legacy_key, str) and legacy_key.strip():
            return legacy_key
        raise SigningKeyError("Falta el archivo privado de configuración de OnStar") from None
    except (OSError, UnicodeError):
        raise SigningKeyError("No se pudo leer la configuración privada de OnStar") from None
    try:
        if len(content) > 16384:
            raise ValueError()
        data = json.loads(content)
        key = data.get("client_secret") if isinstance(data, dict) else None
        if not isinstance(key, str) or not key.strip():
            raise ValueError()
        return key
    except (ValueError, TypeError):
        raise SigningKeyError("El archivo privado de OnStar necesita un client_secret válido") from None


def make_client(settings, key_path):
    # File reads and pair updates run from login in HA's executor.
    client = OnStarClient(settings["username"], settings["password"], "",
                          settings["device_id"], settings.get("client_id", APP_CLIENT_ID))
    def load():
        configuration = load_client_configuration(settings, key_path)
        client.client_id = configuration["client_id"]
        client.app_version = configuration["app_version"]
        return configuration["client_secret"]
    client._client_secret_loader = load
    return client


def load_client_configuration(settings, key_path):
    """UI overrides win; legacy private files and entries remain supported."""
    configuration = dict(APP_DEFAULTS)
    configuration.update({key: settings[key] for key in configuration if settings.get(key)})
    if not settings.get("client_configuration_override"):
        try:
            with Path(key_path).open(encoding="utf-8-sig") as handle:
                content = handle.read(16385)
            if len(content) > 16384:
                raise ValueError()
            private = json.loads(content)
            if not isinstance(private, dict) or not private.get("client_secret"):
                raise ValueError()
            configuration.update({key: private[key] for key in configuration if key in private})
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError, ValueError, TypeError):
            raise SigningKeyError("Configuración del cliente inválida") from None
    for key in ("client_id", "client_secret", "app_version"):
        if not isinstance(configuration.get(key), str) or not configuration[key].strip():
            raise SigningKeyError("Configuración del cliente incompleta")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", configuration["app_version"]):
        raise SigningKeyError("Versión de la aplicación inválida")
    if not re.fullmatch(r"[A-Za-z0-9_]+", configuration["client_id"]):
        raise SigningKeyError("Identificador del cliente inválido")
    return configuration
