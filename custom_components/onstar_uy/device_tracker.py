"""Show GM's cached position on the Home Assistant map."""
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    state = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OnStarTracker(state)])


class OnStarTracker(CoordinatorEntity, TrackerEntity):
    _attr_name = "Chevrolet Ubicación"
    _attr_should_poll = False

    def __init__(self, state):
        super().__init__(state["coordinator"])
        self._attr_unique_id = state["vin"] + "_location"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, state["vin"])}, "name": "Chevrolet OnStar",
            "manufacturer": "Chevrolet", "model": state["vehicle"].get("model"),
        }

    @property
    def available(self):
        return super().available and bool(self.coordinator.data.get("location"))

    @property
    def source_type(self):
        return SourceType.GPS

    @property
    def latitude(self):
        return (self.coordinator.data.get("location") or {}).get("latitude")

    @property
    def longitude(self):
        return (self.coordinator.data.get("location") or {}).get("longitude")

    @property
    def extra_state_attributes(self):
        position = self.coordinator.data.get("location") or {}
        return {"actualizado_por_vehiculo": position.get("updated_at"),
                "actualizacion_pendiente": position.get("update_pending"),
                "resultado_actualizacion": self.coordinator.data.get("refresh", {}).get("location")}
