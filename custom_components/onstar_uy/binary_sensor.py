"""Fluid warnings with explicit unknown handling."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    state = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FluidWarning(state, "BRAKE_FLUID_LOW", "Líquido de frenos bajo"),
                        FluidWarning(state, "WASHER_FLUID_LOW", "Líquido limpiaparabrisas bajo")])


class FluidWarning(CoordinatorEntity, BinarySensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, state, key, name):
        super().__init__(state["coordinator"])
        self.key = key
        self._attr_name = name
        self._attr_unique_id = state["vin"] + "_" + key.lower()
        self._attr_device_info = {"identifiers": {(DOMAIN, state["vin"])}}

    @property
    def is_on(self):
        value = self.coordinator.data["readings"].get(self.key, {}).get("value")
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.upper() in ("TRUE", "FALSE"):
            return value.upper() == "TRUE"
        return None

    @property
    def extra_state_attributes(self):
        return {"actualizado_por_vehiculo": self.coordinator.data["readings"].get(self.key, {}).get("updated_at")}
