# storeSettings.py

import os

from . import displayFormats, storeMemory

SETTINGS_FILE_NAME = "settings.json"

_cached = None


def getSettingsPath():
	return os.path.join(storeMemory.getStateFolder(), SETTINGS_FILE_NAME)


def _defaults():
	return {"abbreviate": True, "format": displayFormats.DEFAULT_FORMAT}


def _clean(raw):
	settings = _defaults()
	if not isinstance(raw, dict):
		return settings
	if isinstance(raw.get("abbreviate"), bool):
		settings["abbreviate"] = raw["abbreviate"]
	if displayFormats.isKnownFormat(raw.get("format")):
		settings["format"] = raw["format"]
	return settings


def get():
	"""Returns the cached settings; the file is read once, then only changed through save()."""
	global _cached
	if _cached is None:
		_cached = _clean(storeMemory.readJsonFile(getSettingsPath()))
	return dict(_cached)


def save(abbreviate, formatKey):
	global _cached
	settings = _clean({"abbreviate": abbreviate, "format": formatKey})
	if not storeMemory.writeJsonFileAtomic(getSettingsPath(), settings):
		return False
	_cached = settings
	return True


def reset():
	global _cached
	_cached = None
