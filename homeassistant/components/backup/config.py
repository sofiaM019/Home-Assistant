"""Provide persistent configuration for the backup integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Self, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


class StoredBackupConfig(TypedDict):
    """Represent the stored backup config."""

    last_automatic_backup: datetime | None


@dataclass(kw_only=True)
class BackupConfigData:
    """Represent loaded backup config data."""

    last_automatic_backup: datetime | None = None

    @classmethod
    def from_dict(cls, data: StoredBackupConfig) -> Self:
        """Initialize backup config data from a dict."""
        return cls(
            last_automatic_backup=data["last_automatic_backup"],
        )

    def to_dict(self) -> StoredBackupConfig:
        """Convert backup config data to a dict."""
        return StoredBackupConfig(
            last_automatic_backup=self.last_automatic_backup,
        )


class BackupConfig:
    """Handle backup config."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize backup config."""
        self.data = BackupConfigData()
        self._hass = hass
        self._store: Store[StoredBackupConfig] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )

    async def load(self) -> None:
        """Load config."""
        stored = await self._store.async_load()
        if stored:
            self.data = BackupConfigData.from_dict(stored)

    async def save(self) -> None:
        """Save config."""
        await self._store.async_save(self.data.to_dict())
