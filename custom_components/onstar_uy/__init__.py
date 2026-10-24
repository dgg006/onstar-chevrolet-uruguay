"""Initial YAML-configured integration for regional OnStar diagnostics."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady

from .client import OnStarAuthError, OnStarError, health_readings
from .credentials import KEY_FILENAME, SigningKeyError, make_client

DOMAIN = "onstar_uy"
LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required("username"): cv.string,
        vol.Required("password"): cv.string,
        vol.Optional("client_secret"): cv.string,
        vol.Required("device_id"): cv.string,
        vol.Optional("client_id", default="OMB_CVY_AND_8T0"): cv.string,
        vol.Optional("app_version", default="8.19.0"): cv.string,
        vol.Optional("vin"): cv.string,
        vol.Optional("scan_interval", default=1800): vol.All(vol.Coerce(int), vol.Range(min=300)),
        vol.Optional("auto_refresh", default=True): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    settings = config.get(DOMAIN)
    if not settings:
        return True
    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=dict(settings)))
    return True


async def async_setup_entry(hass, entry):
    settings = entry.data
    client = make_client(settings, hass.config.path(KEY_FILENAME))
    try:
        vehicles = await hass.async_add_executor_job(client.vehicles)
        vin = settings.get("vin")
        if vin:
            vehicle = next((item for item in vehicles if item.get("vin") == vin), None)
        elif len(vehicles) == 1:
            vehicle = vehicles[0]
            vin = vehicle.get("vin")
        else:
            raise ConfigEntryError("Configurá el VIN para seleccionar uno de los vehículos de la cuenta")
        if not vehicle or not vin:
            raise ConfigEntryError("El vehículo configurado no aparece en esta cuenta")
    except SigningKeyError as error:
        raise ConfigEntryError(str(error)) from error
    except OnStarAuthError as error:
        raise ConfigEntryAuthFailed(str(error)) from error
    except OnStarError as error:
        raise ConfigEntryNotReady(str(error)) from error

    state = {"force_refresh": False, "last_location": None}

    def timestamp(position):
        try:
            return datetime.fromisoformat(position["updated_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        except (KeyError, TypeError, ValueError, AttributeError):
            return datetime.min.replace(tzinfo=timezone.utc)

    async def update():
        try:
            refresh = {"health": "CACHED", "location": "CACHED", "position": None}
            if settings.get("auto_refresh", True) or state["force_refresh"]:
                state["force_refresh"] = False
                refresh = await hass.async_add_executor_job(client.refresh, vin)
            result = await hass.async_add_executor_job(client.health, vin)
            readings = health_readings(result)
            try:
                extra = await hass.async_add_executor_job(client.extra_readings, vin)
                for key, value in extra.items():
                    if readings.get(key, {}).get("value") is None:
                        readings[key] = value
                extra_status = "DATOS_RECIBIDOS" if extra else "SIN_DATOS"
            except OnStarAuthError:
                raise
            except OnStarError as error:
                LOGGER.debug("Consulta experimental no disponible: %s", error)
                extra_status = "ERROR"
            try:
                position = await hass.async_add_executor_job(client.location, vin)
            except OnStarAuthError:
                raise
            except OnStarError as error:
                LOGGER.debug("Ubicación OnStar no disponible: %s", error)
                position = None
            candidates = [p for p in [position, refresh.get("position"), state["last_location"]] if p]
            position = max(candidates, key=timestamp) if candidates else None
            state["last_location"] = position
            return {"readings": readings, "location": position, "extra_status": extra_status,
                    "refresh": {key: refresh[key] for key in ("health", "location")}}
        except OnStarAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except OnStarError as error:
            raise UpdateFailed(str(error)) from error

    coordinator = DataUpdateCoordinator(
        hass, LOGGER, name=DOMAIN, update_method=update,
        config_entry=entry,
        update_interval=timedelta(seconds=settings["scan_interval"]),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator, "vin": vin, "vehicle": vehicle, "state": state,
        "client": client, "entry": entry, "control_lock": asyncio.Lock()}
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "device_tracker", "button"])
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, ["sensor", "binary_sensor", "device_tracker", "button"])
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
