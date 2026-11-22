# addonDownload.py

import hashlib
import http.client
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import addonHandler
import core
import tones
import ui
import wx
from logHandler import log

from . import storeMemory, storeSettings

addonHandler.initTranslation()

# Store add-ons are a few megabytes; a response near this size is not an add-on
_MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_REQUEST_TIMEOUT_SECONDS = 30
_MAX_SPOKEN_LENGTH = 80
# Gives the focus announcement after the context menu closes time to finish before the start message
_START_MESSAGE_DELAY_MS = 500
_DONE_BEEP_HZ = 880
_DONE_BEEP_MS = 150
_ADDON_EXTENSION = ".nvda-addon"
_URL_ATTRIBUTE_NAMES = ("URL", "downloadURL", "downloadUrl")
_INVALID_FILE_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Looking up the size is a courtesy, so it gets a short timeout and a small cache
_SIZE_TIMEOUT_SECONDS = 10
_SIZE_CACHE_MAX_ENTRIES = 200
# The size of the latest known version of each add-on is kept in a JSON file
_SIZES_FILE_NAME = "addonSizes.json"
_STORED_SIZES_MAX_ENTRIES = 3000
_SIZE_RETRY_AFTER_FAILURE_SECONDS = 300
_CONTENT_RANGE_TOTAL = re.compile(r"bytes \d+-\d+/(\d+)")

_stopRequested = threading.Event()
_activeWorker = None
_startMessageTimer = None
_sizeWorker = None
_sizeLock = threading.Lock()
# Download address -> (size in bytes or 0 when unknown, time of the lookup); holds failed lookups
# and the sizes of add-ons without a usable id and version
_sizeCache = {}
# "addonId|channel" -> {"version": version name, "size": bytes}, mirrored in the JSON file;
# one entry per add-on, replaced when a new version appears
_storedSizes = {}


class _DownloadError(Exception):
	pass


def getSizesPath():
	return os.path.join(storeMemory.getStateFolder(), _SIZES_FILE_NAME)


def _cleanSizes(raw):
	sizes = {}
	rawSizes = raw.get("sizes") if isinstance(raw, dict) else None
	if not isinstance(rawSizes, dict):
		return sizes
	for key, entry in rawSizes.items():
		if not isinstance(key, str) or not isinstance(entry, dict):
			continue
		versionName = entry.get("version")
		size = entry.get("size")
		if isinstance(versionName, str) and versionName and isinstance(size, int) and not isinstance(size, bool) and size > 0:
			sizes[key] = {"version": versionName, "size": size}
	return dict(list(sizes.items())[-_STORED_SIZES_MAX_ENTRIES:])


def prepare():
	global _storedSizes
	_stopRequested.clear()
	_storedSizes = _cleanSizes(storeMemory.readJsonFile(getSizesPath()))


def stop():
	global _activeWorker, _startMessageTimer, _sizeWorker
	_stopRequested.set()
	_activeWorker = None
	_sizeWorker = None
	if _startMessageTimer is not None:
		_startMessageTimer.Stop()
		_startMessageTimer = None


def getDownloadUrl(model):
	for attributeName in _URL_ATTRIBUTE_NAMES:
		value = getattr(model, attributeName, None)
		if not isinstance(value, str):
			continue
		address = value.strip()
		parts = urllib.parse.urlparse(address)
		if parts.scheme == "https" and parts.netloc:
			return address
	return ""


def _shorten(text):
	if len(text) <= _MAX_SPOKEN_LENGTH:
		return text
	# Translators: Appended to a spoken add-on or file name that was cut short
	return text[:_MAX_SPOKEN_LENGTH] + _("... shortened")


def _suggestFileName(model, url):
	urlName = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(url).path))
	fileName = _INVALID_FILE_NAME_CHARS.sub("_", urlName).strip(" .")
	if fileName.lower().endswith(_ADDON_EXTENSION):
		return fileName
	addonId = str(getattr(model, "addonId", "") or "addon")
	versionName = str(getattr(model, "addonVersionName", "") or "")
	baseName = f"{addonId}-{versionName}" if versionName else addonId
	return _INVALID_FILE_NAME_CHARS.sub("_", baseName) + _ADDON_EXTENSION


def formatSize(sizeBytes):
	"""Returns a short size such as 300 KB or 1.56 MB (1024-based, as Windows shows file sizes)."""
	if sizeBytes < 1024:
		return f"{sizeBytes} B"
	if sizeBytes < 1024 * 1024:
		return f"{round(sizeBytes / 1024)} KB"
	if sizeBytes < 1024 * 1024 * 1024:
		return f"{sizeBytes / (1024 * 1024):.2f} MB"
	return f"{sizeBytes / (1024 * 1024 * 1024):.2f} GB"


def _sizeIdentity(model):
	"""Returns the JSON key and the version name of an add-on, or two empty strings when it has no usable id and version."""
	addonId = getattr(model, "addonId", "")
	versionName = getattr(model, "addonVersionName", "")
	if not (isinstance(addonId, str) and isinstance(versionName, str) and addonId and versionName):
		return "", ""
	channel = getattr(model, "channel", "")
	channelName = str(getattr(channel, "value", channel) or "")
	return f"{addonId}|{channelName}", versionName


def requestSize(model, onSize):
	"""Calls onSize(sizeBytes) on the main thread once the size of the add-on file is known.

	A size remembered for this exact add-on version is reported at once, without any network request.
	For a new version, or an unknown add-on, one background lookup runs and its result replaces the
	old entry; none is started while another is running or shortly after one failed for this address.
	"""
	global _sizeWorker
	url = getDownloadUrl(model)
	key, versionName = _sizeIdentity(model)
	stored = _storedSizes.get(key) if key else None
	if stored and stored["version"] == versionName:
		onSize(stored["size"])
		return
	cached = _sizeCache.get(url)
	if cached:
		if cached[0]:
			onSize(cached[0])
			return
		if time.monotonic() - cached[1] < _SIZE_RETRY_AFTER_FAILURE_SECONDS:
			return
	if _sizeWorker is not None and _sizeWorker.is_alive():
		return
	worker = threading.Thread(
		target=_lookUpSize,
		args=(url, key, versionName, onSize),
		name="addonStoreLiteSize",
		daemon=True,
	)
	_sizeWorker = worker
	worker.start()


def _fetchSize(url):
	# A one byte range request works even where the server refuses HEAD, and nothing else is read
	request = urllib.request.Request(url, headers={"User-Agent": "addonStoreLite", "Range": "bytes=0-0"})
	with urllib.request.urlopen(request, timeout=_SIZE_TIMEOUT_SECONDS) as response:
		rangeMatch = _CONTENT_RANGE_TOTAL.fullmatch((response.headers.get("Content-Range") or "").strip())
		if rangeMatch:
			return int(rangeMatch.group(1))
		if response.status == 200:
			return int(response.headers.get("Content-Length") or 0)
	return 0


def _rememberSize(key, versionName, sizeBytes):
	with _sizeLock:
		_storedSizes.pop(key, None)
		_storedSizes[key] = {"version": versionName, "size": sizeBytes}
		while len(_storedSizes) > _STORED_SIZES_MAX_ENTRIES:
			del _storedSizes[next(iter(_storedSizes))]
		snapshot = dict(_storedSizes)
	storeMemory.writeJsonFileAtomic(getSizesPath(), {"sizes": snapshot})


def _lookUpSize(url, key, versionName, onSize):
	sizeBytes = 0
	try:
		sizeBytes = _fetchSize(url)
	except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
		log.debug(f"addonStoreLite: could not read the add-on size: {e}")
	if _stopRequested.is_set():
		return
	if sizeBytes > 0 and key:
		_rememberSize(key, versionName, sizeBytes)
	else:
		if len(_sizeCache) >= _SIZE_CACHE_MAX_ENTRIES:
			_sizeCache.clear()
		_sizeCache[url] = (sizeBytes, time.monotonic())
	if sizeBytes > 0:
		wx.CallAfter(onSize, sizeBytes)


def beginDownload(model):
	global _activeWorker, _startMessageTimer
	url = getDownloadUrl(model)
	if not url:
		# Translators: Spoken when the selected add-on has no usable download address
		ui.message(_("This add-on has no download address"))
		return
	if _activeWorker is not None and _activeWorker.is_alive():
		# Translators: Spoken when the user starts a second download while one is still running
		ui.message(_("A download is already in progress"))
		return
	targetPath = os.path.join(storeSettings.getDownloadFolder(), _suggestFileName(model, url))
	expectedHash = str(getattr(model, "sha256", "") or "").strip().lower()
	displayName = _shorten(str(getattr(model, "displayName", "") or os.path.basename(targetPath)))
	# Translators: Spoken when an add-on download starts; {name} is the add-on name
	startMessage = _("Downloading {name}").format(name=displayName)
	_startMessageTimer = core.callLater(_START_MESSAGE_DELAY_MS, ui.message, startMessage)
	worker = threading.Thread(
		target=_downloadFile,
		args=(url, targetPath, expectedHash),
		name="addonStoreLiteDownload",
		daemon=True,
	)
	_activeWorker = worker
	worker.start()


def _fetchToFile(url, partPath, expectedHash):
	digest = hashlib.sha256()
	received = 0
	request = urllib.request.Request(url, headers={"User-Agent": "addonStoreLite"})
	with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
		declaredLength = int(response.headers.get("Content-Length") or 0)
		if declaredLength > _MAX_DOWNLOAD_BYTES:
			# Translators: Spoken when the file offered for download is unreasonably large
			raise _DownloadError(_("Download failed: the file is too large"))
		with open(partPath, "wb") as partFile:
			while True:
				if _stopRequested.is_set():
					raise _DownloadError("stopped")
				chunk = response.read(_READ_CHUNK_BYTES)
				if not chunk:
					break
				received += len(chunk)
				if received > _MAX_DOWNLOAD_BYTES:
					raise _DownloadError(_("Download failed: the file is too large"))
				digest.update(chunk)
				partFile.write(chunk)
			partFile.flush()
			os.fsync(partFile.fileno())
	if not received:
		# Translators: Spoken when the server returned no data
		raise _DownloadError(_("Download failed: the file was empty"))
	if expectedHash and digest.hexdigest() != expectedHash:
		# Translators: Spoken when the downloaded file does not match the checksum published by the store
		raise _DownloadError(_("Download failed: the file did not match its checksum"))


def _removeIfPresent(path):
	try:
		if os.path.isfile(path):
			os.unlink(path)
	except OSError as e:
		log.warning(f"addonStoreLite: could not remove {path}: {e}")


def _downloadFile(url, targetPath, expectedHash):
	partPath = targetPath + ".part"
	resultMessage = ""
	try:
		os.makedirs(os.path.dirname(targetPath), exist_ok=True)
		_fetchToFile(url, partPath, expectedHash)
		os.replace(partPath, targetPath)
		log.info("addonStoreLite: download completed")
	except _DownloadError as e:
		log.warning(f"addonStoreLite: download rejected: {e}")
		resultMessage = str(e)
	except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
		log.warning(f"addonStoreLite: download failed: {e}")
		# Translators: Spoken when an add-on download failed because of a network or file error
		resultMessage = _("Download failed")
	finally:
		_removeIfPresent(partPath)
	if _stopRequested.is_set():
		return
	if resultMessage:
		wx.CallAfter(ui.message, resultMessage)
	else:
		wx.CallAfter(tones.beep, _DONE_BEEP_HZ, _DONE_BEEP_MS)
