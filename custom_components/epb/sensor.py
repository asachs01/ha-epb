"""Support for EPB sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorStateClass)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EPBUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EPB sensor."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for account in coordinator.account_links:
        account_id = account["power_account"]["account_id"]
        entities.extend(
            [
                EPBEnergySensor(coordinator, account_id),
                EPBCostSensor(coordinator, account_id),
            ]
        )

    async_add_entities(entities)


class EPBSensorBase(CoordinatorEntity[EPBUpdateCoordinator], SensorEntity):
    """Base class for EPB sensors."""

    def __init__(
        self,
        coordinator: EPBUpdateCoordinator,
        account_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.account_id = account_id
        self._attr_has_entity_name = True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "account_id": self.account_id,
        }


class EPBEnergySensor(EPBSensorBase):
    """Sensor for EPB energy usage."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        coordinator: EPBUpdateCoordinator,
        account_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account_id)
        # Use the correct naming convention for the unique_id
        self._attr_unique_id = f"epb_energy_{account_id}"
        # Set the entity_id to match the expected pattern
        self.entity_id = f"sensor.epb_energy_{account_id}"
        self._attr_name = f"EPB Energy {account_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or self.account_id not in self.coordinator.data:
            return None

        kwh = self.coordinator.data[self.account_id].get("kwh")
        return float(kwh) if kwh is not None else None


class EPBCostSensor(EPBSensorBase):
    """Sensor for EPB energy cost."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "$"

    def __init__(
        self,
        coordinator: EPBUpdateCoordinator,
        account_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account_id)
        # Use the correct naming convention for the unique_id
        self._attr_unique_id = f"epb_cost_{account_id}"
        # Set the entity_id to match the expected pattern
        self.entity_id = f"sensor.epb_cost_{account_id}"
        self._attr_name = f"EPB Cost {account_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or self.account_id not in self.coordinator.data:
            return None

        cost = self.coordinator.data[self.account_id].get("cost")
        return float(cost) if cost is not None else None
