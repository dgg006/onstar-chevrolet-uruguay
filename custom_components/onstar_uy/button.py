"""Refresh data and send the six observed vehicle controls."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError

from . import DOMAIN
from .client import OnStarError

CONTROL_BUTTONS = (
    ("lock", "Bloquear puertas", "mdi:lock"),
    ("unlock", "Desbloquear puertas", "mdi:lock-open"),
    ("flash", "Destellar luces", "mdi:car-light-high"),
    ("cancel_flash", "Apagar destellos", "mdi:car-light-dimmed"),
    ("honk", "Activar bocina", "mdi:bullhorn"),
    ("cancel_honk", "Apagar bocina", "mdi:bullhorn-outline"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    state = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OnStarRefreshButton(state)] + [
        OnStarControlButton(state, *control) for control in CONTROL_BUTTONS])


class OnStarControlButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_available = True

    def __init__(self, state, action, name, icon):
        self._client = state["client"]
        self._vin = state["vin"]
        self._action = action
        self._control_lock = state["control_lock"]
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = self._vin + "_control_" + action
        self._attr_device_info = {"identifiers": {(DOMAIN, self._vin)}}
        self._result = "SIN_EJECUTAR"

    async def async_press(self):
        # Stops remain usable while a previous command awaits confirmation.
        stop = self._action.startswith("cancel_")
        if not stop and self._control_lock.locked():
            raise HomeAssistantError("Ya hay un control en curso; esperá su resultado")
        self._result = "EN_CURSO"
        self.async_write_ha_state()
        try:
            if stop:
                self._result = await self.hass.async_add_executor_job(
                    self._client.control, self._vin, self._action)
            else:
                async with self._control_lock:
                    self._result = await self.hass.async_add_executor_job(
                        self._client.control, self._vin, self._action)
        except OnStarError as error:
            self._result = "NO_CONFIRMADO"
            raise HomeAssistantError(str(error)) from error
        finally:
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"resultado_ultimo_comando": self._result}


class OnStarRefreshButton(CoordinatorEntity, ButtonEntity):
    _attr_name = "Actualizar datos"
    _attr_has_entity_name = True
    _attr_icon = "mdi:refresh"

    def __init__(self, state):
        super().__init__(state["coordinator"])
        self._refresh_state = state["state"]
        self._attr_unique_id = state["vin"] + "_refresh"
        self._attr_device_info = {"identifiers": {(DOMAIN, state["vin"])}}

    async def async_press(self):
        self._refresh_state["force_refresh"] = True
        await self.coordinator.async_request_refresh()

    @property
    def available(self):
        # Allow a manual retry even after a failed remote query.
        return True

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("refresh", {})
