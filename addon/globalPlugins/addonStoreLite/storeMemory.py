# storeMemory.py

import json
import os

import globalVars
from logHandler import log

STATE_FILE_NAME = "storeState.json"
KNOWN_TABS = ("INSTALLED", "UPDATE", "AVAILABLE", "INCOMPATIBLE")
# Every per-tab mapping kept in the state file besides the sort entries
_NAME_MAPS = ("channels", "enabled")


def getStateFolder():
	return os.path.join(globalVars.appArgs.configPath, "ChaiChaimee", "addonStoreLite")


def getStatePath():
	return os.path.join(getStateFolder(), STATE_FILE_NAME)


def readJsonFile(path):
	"""Returns the parsed content of path (or of its .bak copy), or None when neither can be read."""
	for candidate in (path, path + ".bak"):
		if not os.path.isfile(candidate):
			continue
		try:
			with open(candidate, "r", encoding="utf-8") as jsonFile:
				return json.load(jsonFile)
		except (OSError, ValueError) as e:
			log.warning(f"addonStoreLite: could not read {candidate}: {e}")
	return None


def writeJsonFileAtomic(path, data):
	tempPath = path + ".tmp"
	try:
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(tempPath, "w", encoding="utf-8") as tempFile:
			json.dump(data, tempFile, indent=2)
			tempFile.flush()
			os.fsync(tempFile.fileno())
		if os.path.isfile(path):
			try:
				os.replace(path, path + ".bak")
			except OSError as e:
				log.warning(f"addonStoreLite: could not refresh backup: {e}")
		os.replace(tempPath, path)
		return True
	except OSError as e:
		log.warning(f"addonStoreLite: could not save {path}: {e}")
		try:
			if os.path.isfile(tempPath):
				os.unlink(tempPath)
		except OSError as cleanupError:
			log.warning(f"addonStoreLite: could not remove {tempPath}: {cleanupError}")
		return False


def _emptyState():
	state = {"lastTab": "", "sorts": {}, "downloadFolder": ""}
	for mapName in _NAME_MAPS:
		state[mapName] = {}
	return state


def _cleanState(raw):
	state = _emptyState()
	if not isinstance(raw, dict):
		return state
	lastTab = raw.get("lastTab")
	if lastTab in KNOWN_TABS:
		state["lastTab"] = lastTab
	downloadFolder = raw.get("downloadFolder")
	if isinstance(downloadFolder, str):
		state["downloadFolder"] = downloadFolder
	sorts = raw.get("sorts")
	if isinstance(sorts, dict):
		for tabName, entry in sorts.items():
			if tabName not in KNOWN_TABS or not isinstance(entry, dict):
				continue
			fieldName = entry.get("field")
			if isinstance(fieldName, str) and fieldName:
				state["sorts"][tabName] = {"field": fieldName, "reverse": bool(entry.get("reverse"))}
	for mapName in _NAME_MAPS:
		saved = raw.get(mapName)
		if not isinstance(saved, dict):
			continue
		for tabName, value in saved.items():
			if tabName in KNOWN_TABS and isinstance(value, str) and value:
				state[mapName][tabName] = value
	return state


def loadState():
	return _cleanState(readJsonFile(getStatePath()))


def saveState(state):
	return writeJsonFileAtomic(getStatePath(), _cleanState(state))


def rememberTab(tabName):
	if tabName not in KNOWN_TABS:
		return
	state = loadState()
	if state["lastTab"] == tabName:
		return
	state["lastTab"] = tabName
	saveState(state)


def rememberDownloadFolder(folderPath):
	if not folderPath:
		return
	state = loadState()
	if state["downloadFolder"] == folderPath:
		return
	state["downloadFolder"] = folderPath
	saveState(state)


def rememberSort(tabName, fieldName, reverse):
	if tabName not in KNOWN_TABS or not fieldName:
		return
	state = loadState()
	entry = {"field": fieldName, "reverse": bool(reverse)}
	if state["sorts"].get(tabName) == entry:
		return
	state["sorts"][tabName] = entry
	saveState(state)


def rememberTabValue(mapName, tabName, value):
	"""Remembers a per-tab filter value (mapName is one of channels or enabled) by its enum member name."""
	if mapName not in _NAME_MAPS or tabName not in KNOWN_TABS or not value:
		return
	state = loadState()
	if state[mapName].get(tabName) == value:
		return
	state[mapName][tabName] = value
	saveState(state)
