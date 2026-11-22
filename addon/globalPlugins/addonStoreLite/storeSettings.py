# storeSettings.py

import ctypes
import os
import uuid
from ctypes import wintypes

from logHandler import log

from . import displayFormats, storeMemory

SETTINGS_FILE_NAME = "settings.json"
# Windows known folder id of the per-user Downloads folder
_FOLDERID_DOWNLOADS = "{374DE290-123F-4565-9164-39C4925E467B}"

_cached = None


def getSettingsPath():
	return os.path.join(storeMemory.getStateFolder(), SETTINGS_FILE_NAME)


def getDefaultDownloadFolder():
	return os.path.join(storeMemory.getStateFolder(), "downloads")


def getSystemDownloadsFolder():
	"""Returns the Windows Downloads folder, the default of browsers; empty when Windows cannot say."""
	folderId = (ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID(_FOLDERID_DOWNLOADS).bytes_le)
	pathPointer = ctypes.c_wchar_p()
	folder = ""
	try:
		getKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
		getKnownFolderPath.argtypes = [
			ctypes.c_void_p,
			wintypes.DWORD,
			wintypes.HANDLE,
			ctypes.POINTER(ctypes.c_wchar_p),
		]
		getKnownFolderPath.restype = ctypes.c_long
		result = getKnownFolderPath(ctypes.byref(folderId), 0, None, ctypes.byref(pathPointer))
		if result == 0:
			folder = pathPointer.value or ""
		if pathPointer:
			ctypes.windll.ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
			ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(pathPointer, ctypes.c_void_p))
	except (AttributeError, OSError) as e:
		log.warning(f"addonStoreLite: could not ask Windows for the Downloads folder: {e}")
	return folder


def _defaults():
	return {"abbreviate": True, "format": displayFormats.DEFAULT_FORMAT, "downloadFolder": ""}


def _clean(raw):
	settings = _defaults()
	if not isinstance(raw, dict):
		return settings
	if isinstance(raw.get("abbreviate"), bool):
		settings["abbreviate"] = raw["abbreviate"]
	if displayFormats.isKnownFormat(raw.get("format")):
		settings["format"] = raw["format"]
	downloadFolder = raw.get("downloadFolder")
	if isinstance(downloadFolder, str) and os.path.isabs(downloadFolder):
		settings["downloadFolder"] = downloadFolder
	return settings


def get():
	"""Returns the cached settings; the file is read once, then only changed through save()."""
	global _cached
	if _cached is None:
		_cached = _clean(storeMemory.readJsonFile(getSettingsPath()))
	return dict(_cached)


def getDownloadFolder():
	"""Returns the folder chosen in the settings panel, else the Windows Downloads folder, else the add-on's own folder."""
	return get()["downloadFolder"] or getSystemDownloadsFolder() or getDefaultDownloadFolder()


def save(abbreviate, formatKey, downloadFolder):
	global _cached
	settings = _clean({"abbreviate": abbreviate, "format": formatKey, "downloadFolder": downloadFolder})
	if not storeMemory.writeJsonFileAtomic(getSettingsPath(), settings):
		return False
	_cached = settings
	return True


def reset():
	global _cached
	_cached = None
