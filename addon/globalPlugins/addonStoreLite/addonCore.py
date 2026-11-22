# addonCore.py

import functools
import re
import time

import addonHandler
import api
import controlTypes
import globalPluginHandler
import globalVars
import logHandler
import ui
import wx
from gui.settingsDialogs import NVDASettingsDialog
from speech.extensions import filter_speechSequence

from . import addonDownload, displayFormats, storeMemory, storeSettings
from .settingsPanel import AddonStoreLiteSettingsPanel

try:
	from comtypes import COMError
except ImportError:
	COMError = Exception

addonHandler.initTranslation()

# Seconds after the store opens during which its opening speech is rewritten
_OPEN_SPEECH_WINDOW = 5.0

# Seconds after the context menu closes during which the dialog re-announcement is dropped
_MENU_RETURN_SILENCE_WINDOW = 3.0

# Tabs whose first context menu entry installs or updates, so Download can follow it
_DOWNLOAD_TABS = ("AVAILABLE", "UPDATE")

# Translators: The word "of" in the "X of Y" item position that NVDA appends to list items
_itemCountPattern = re.compile(r"(\s+\d+\s+" + re.escape(_("of")) + r"\s+\d+)$")


def _getListField(fieldName):
	try:
		from gui.addonStoreGui.viewModels.addonList import AddonListField
	except ImportError:
		return None
	return getattr(AddonListField, fieldName, None)


def _getChoiceFields(listVM):
	# NVDA 2026.2 and later list Relevance first (sortableFields); 2025.x uses the visible columns only
	fields = getattr(listVM, "sortableFields", None)
	if fields is None:
		fields = listVM.presentedFields
	return list(fields)


def _getTabName(dialog):
	return dialog._statusFilterKey.name


def _prepareTabChange(dialog):
	# NVDA 2026.2+ keeps the sort field across tabs and looks up its index in the new tab's column list.
	# A field hidden on the new tab (install date on Available) would make that lookup fail.
	listVM = dialog._storeVM.listVM
	if not hasattr(listVM, "_prevSortByModelField"):
		return
	from gui.addonStoreGui.viewModels.addonList import AddonListField

	newKey = dialog._statusFilterKey
	oldKey = dialog._storeVM._filteredStatusKey

	def validEverywhere(field):
		if field.name == "searchRank":
			return True
		return newKey not in field.hideStatuses and oldKey not in field.hideStatuses

	safeField = _getListField("publicationDate") or AddonListField.displayName
	if not validEverywhere(listVM._sortByModelField):
		listVM._sortByModelField = safeField
	if not validEverywhere(listVM._prevSortByModelField):
		listVM._prevSortByModelField = safeField


def _applyRememberedSort(dialog):
	listVM = dialog._storeVM.listVM
	fields = _getChoiceFields(listVM)
	saved = storeMemory.loadState()["sorts"].get(_getTabName(dialog))
	field = _getListField(saved["field"]) if saved else None
	if field is None or field not in fields:
		# Keep NVDA's own sort, but make the combo box match the real sort (needed after _prepareTabChange)
		current = listVM._sortByModelField
		if current in fields:
			reverse = bool(getattr(listVM, "_reverseSort", False))
			dialog.columnFilterCtrl.SetSelection(fields.index(current) * 2 + (1 if reverse else 0))
		return
	reverse = saved["reverse"]
	listVM.setSortField(field, reverse)
	# NVDA 2026.2+ restores this pair after the search box is cleared
	if hasattr(listVM, "_prevSortByModelField"):
		listVM._prevSortByModelField = field
	if hasattr(listVM, "_prevReverseSort"):
		listVM._prevReverseSort = reverse
	dialog.columnFilterCtrl.SetSelection(fields.index(field) * 2 + (1 if reverse else 0))


def _applyRememberedFilters(dialog):
	from addonStore.models.channel import Channel
	from addonStore.models.status import EnabledStatus, _StatusFilterKey

	state = storeMemory.loadState()
	tabName = _getTabName(dialog)
	storeVM = dialog._storeVM
	channel = Channel.__members__.get(state["channels"].get(tabName, ""))
	if channel is not None:
		ctrl = dialog.channelFilterCtrl
		shown = [ctrl.GetString(index) for index in range(ctrl.GetCount())]
		# The External channel is only offered on the Installed and Incompatible tabs
		if channel.displayString in shown:
			storeVM._filterChannelKey = channel
	if storeVM._filteredStatusKey in (_StatusFilterKey.AVAILABLE, _StatusFilterKey.UPDATE):
		return
	enabled = EnabledStatus.__members__.get(state["enabled"].get(tabName, ""))
	if enabled is not None:
		storeVM._filterEnabledDisabled = enabled
		dialog.enabledFilterCtrl.SetSelection(list(EnabledStatus).index(enabled))


def _findStoreDialog(window):
	current = window
	for _level in range(6):
		if current is None:
			return None
		if hasattr(current, "_storeVM"):
			return current
		current = current.GetParent()
	return None


def _copyDownloadUrl(model):
	if api.copyToClip(addonDownload.getDownloadUrl(model)):
		# Translators: Spoken after the add-on download address was copied to the clipboard
		ui.message(_("Download URL copied"))
	else:
		# Translators: Spoken when the add-on download address could not be copied
		ui.message(_("Could not copy the download URL"))


def _showDownloadSize(menu, itemId, sizeBytes):
	# The size arrives while the menu may already be open, so the label is changed in place
	if not menu.FindItemById(itemId):
		return
	# Translators: Context menu item in the Add-on Store that saves the add-on file; {size} is its size such as 1.56 MB
	menu.SetLabel(itemId, _("&Download {size}").format(size=addonDownload.formatSize(sizeBytes)))


def _addDownloadItem(menu, targetWindow):
	# NVDA may reuse the same wx.Menu between pop-ups, so drop the item added last time first
	for staleItemId in getattr(menu, "_liteDownloadItemIds", ()):
		if menu.FindItemById(staleItemId):
			menu.Delete(staleItemId)
	menu._liteDownloadItemIds = ()
	dialog = _findStoreDialog(targetWindow)
	if dialog is None or _getTabName(dialog) not in _DOWNLOAD_TABS:
		return
	selectedItem = dialog._storeVM.listVM.getSelection()
	if selectedItem is None or not addonDownload.getDownloadUrl(selectedItem.model):
		return
	if menu.GetMenuItemCount() == 0:
		return
	model = selectedItem.model
	# Translators: Context menu item in the Add-on Store that saves the add-on file to the download destination
	downloadItem = menu.Insert(1, wx.ID_ANY, _("&Download"))
	downloadItemId = downloadItem.GetId()
	addonDownload.requestSize(model, lambda sizeBytes: _showDownloadSize(menu, downloadItemId, sizeBytes))
	menu.Bind(wx.EVT_MENU, lambda event: addonDownload.beginDownload(model), downloadItem)
	# Translators: Context menu item in the Add-on Store that copies the add-on download address to the clipboard
	copyUrlItem = menu.Insert(2, wx.ID_ANY, _("Copy download &URL"))
	menu.Bind(wx.EVT_MENU, lambda event: _copyDownloadUrl(model), copyUrlItem)
	menu._liteDownloadItemIds = (downloadItem.GetId(), copyUrlItem.GetId())


def _recordChannel(dialog):
	storeMemory.rememberTabValue("channels", _getTabName(dialog), dialog._storeVM._filterChannelKey.name)


def _recordEnabled(dialog):
	storeMemory.rememberTabValue("enabled", _getTabName(dialog), dialog._storeVM._filterEnabledDisabled.name)


def _recordSort(dialog):
	listVM = dialog._storeVM.listVM
	field = listVM._sortByModelField
	if field.name == "searchRank":
		# Relevance only exists while searching
		return
	storeMemory.rememberSort(_getTabName(dialog), field.name, bool(getattr(listVM, "_reverseSort", False)))


def _recordTab(dialog):
	storeMemory.rememberTab(_getTabName(dialog))


def _tabToOpen(requested):
	# A tab NVDA asked for explicitly (for example Updatable add-ons from the update notification) wins
	if requested is not None:
		return requested
	lastTab = storeMemory.loadState()["lastTab"]
	if not lastTab:
		return requested
	from addonStore.models.status import _StatusFilterKey

	return getattr(_StatusFilterKey, lastTab, requested)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		# State toggle acting as a watchdog sleep/wake mechanism
		self._isStoreActive = False
		self._patched = []
		self._openSpeech = None
		self._menuReturnSilence = None
		self._speechFilterRegistered = False
		# Translators: Log message when the add-on is loaded
		logHandler.log.info(_("addonStoreLite loaded"))
		if globalVars.appArgs.secure:
			return
		# Loaded here so the settings panel and focus handler only ever read the cached values
		storeSettings.get()
		addonDownload.prepare()
		NVDASettingsDialog.categoryClasses.append(AddonStoreLiteSettingsPanel)
		try:
			self._patchStore()
		except Exception:
			logHandler.log.exception("addonStoreLite: could not attach to the Add-on Store")
		try:
			self._patchContextMenu()
		except Exception:
			logHandler.log.exception("addonStoreLite: could not add Download to the context menu")

	def terminate(self):
		# Strict cleanup to prevent zombie state
		addonDownload.stop()
		self._isStoreActive = False
		self._openSpeech = None
		self._menuReturnSilence = None
		if AddonStoreLiteSettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(AddonStoreLiteSettingsPanel)
		if self._speechFilterRegistered:
			filter_speechSequence.unregister(self._filterOpenSpeech)
			self._speechFilterRegistered = False
		for cls, name, original in reversed(self._patched):
			setattr(cls, name, original)
		self._patched = []
		super(GlobalPlugin, self).terminate()

	def _wrap(self, cls, name, before=None, after=None, getDialog=lambda obj: obj):
		original = getattr(cls, name)

		@functools.wraps(original)
		def wrapper(obj, *args, **kwargs):
			if before:
				try:
					before(getDialog(obj))
				except Exception:
					logHandler.log.exception(f"addonStoreLite: error before {name}")
			result = original(obj, *args, **kwargs)
			if after:
				try:
					after(getDialog(obj))
				except Exception:
					logHandler.log.exception(f"addonStoreLite: error after {name}")
			return result

		setattr(cls, name, wrapper)
		self._patched.append((cls, name, original))

	def _wrapInit(self, cls):
		original = cls.__init__

		@functools.wraps(original)
		def wrapper(obj, parent, storeVM, *args, **kwargs):
			if args:
				requested, args = args[0], args[1:]
			else:
				requested = kwargs.pop("openToTab", None)
			try:
				requested = _tabToOpen(requested)
			except Exception:
				logHandler.log.exception("addonStoreLite: error choosing the opening tab")
			original(obj, parent, storeVM, requested, *args, **kwargs)
			try:
				self._armOpenSpeech(obj)
			except Exception:
				logHandler.log.exception("addonStoreLite: error preparing the opening announcement")

		cls.__init__ = wrapper
		self._patched.append((cls, "__init__", original))

	def _wrapPopup(self, cls, name):
		original = getattr(cls, name)

		@functools.wraps(original)
		def wrapper(menuObj, *args, **kwargs):
			targetWindow = next((arg for arg in (*args, *kwargs.values()) if isinstance(arg, wx.Window)), None)
			menuClassName = type(menuObj).__name__
			if targetWindow is None or "Batch" in menuClassName or "SubMenu" in menuClassName:
				return original(menuObj, *args, **kwargs)
			originalPopup = targetWindow.PopupMenu

			def popupWithDownload(menu, *popupArgs, **popupKwargs):
				try:
					_addDownloadItem(menu, targetWindow)
				except Exception:
					logHandler.log.exception("addonStoreLite: error adding the Download item")
				self._armMenuReturnSilence(targetWindow)
				try:
					return originalPopup(menu, *popupArgs, **popupKwargs)
				finally:
					self._startMenuReturnSilenceWindow()

			try:
				targetWindow.PopupMenu = popupWithDownload
			except (AttributeError, TypeError):
				logHandler.log.debug("addonStoreLite: could not intercept the context menu pop-up")
				return original(menuObj, *args, **kwargs)
			try:
				return original(menuObj, *args, **kwargs)
			finally:
				vars(targetWindow).pop("PopupMenu", None)

		setattr(cls, name, wrapper)
		self._patched.append((cls, name, original))

	def _patchContextMenu(self):
		from gui.addonStoreGui.controls import actions as storeActions

		# Batch menus (several selected add-ons) are left alone; Download applies to one add-on
		hookedNames = []
		for className, menuClass in vars(storeActions).items():
			if not isinstance(menuClass, type) or menuClass.__module__ != storeActions.__name__:
				continue
			if "Batch" in className or getattr(menuClass, "_is_protocol", False):
				continue
			for methodName, member in list(vars(menuClass).items()):
				if "popup" in methodName.lower() and callable(member):
					self._wrapPopup(menuClass, methodName)
					hookedNames.append(f"{className}.{methodName}")
		if not hookedNames:
			logHandler.log.warning("addonStoreLite: no context menu pop-up method found, Download is unavailable")
			return
		logHandler.log.info(f"addonStoreLite: Download hooked into {', '.join(hookedNames)}")

	def _patchStore(self):
		from gui.addonStoreGui.controls.storeDialog import AddonStoreDialog
		from gui.addonStoreGui.controls.addonList import AddonVirtualList

		def afterTabChange(dialog):
			_applyRememberedSort(dialog)
			_recordTab(dialog)

		self._wrap(AddonStoreDialog, "onListTabPageChange", before=_prepareTabChange, after=afterTabChange)
		self._wrapInit(AddonStoreDialog)
		self._wrap(AddonStoreDialog, "_toggleFilterControls", after=_applyRememberedFilters)
		self._wrap(AddonStoreDialog, "onColumnFilterChange", after=_recordSort)
		self._wrap(AddonStoreDialog, "onChannelFilterChange", after=_recordChannel)
		self._wrap(AddonStoreDialog, "onEnabledFilterChange", after=_recordEnabled)
		if hasattr(AddonVirtualList, "OnColClick"):
			self._wrap(AddonVirtualList, "OnColClick", after=_recordSort, getDialog=lambda lst: lst.Parent)
		filter_speechSequence.register(self._filterOpenSpeech)
		self._speechFilterRegistered = True

	def _armOpenSpeech(self, dialog):
		tabName = dialog._statusFilterKey.displayString
		self._openSpeech = {
			"deadline": time.monotonic() + _OPEN_SPEECH_WINDOW,
			"title": str(dialog.title),
			"listLabel": dialog.listLabel.GetLabel().replace("&", ""),
			"announcement": f"{tabName} {controlTypes.Role.TAB.displayString} {controlTypes.State.SELECTED.displayString}",
			"announced": False,
		}

	def _armMenuReturnSilence(self, targetWindow):
		# Closing the context menu, by Escape or by choosing an item, makes NVDA re-announce the dialog
		# title, the details of the selected add-on and the list label, though focus is still on the
		# same list item. Armed while the menu is open; the time limit only starts once it closes.
		self._menuReturnSilence = None
		try:
			dialog = _findStoreDialog(targetWindow)
			if dialog is None:
				return
			self._menuReturnSilence = {
				"deadline": float("inf"),
				"title": str(dialog.title),
				"listLabel": dialog.listLabel.GetLabel().replace("&", ""),
			}
		except Exception:
			logHandler.log.exception("addonStoreLite: could not silence the dialog re-announcement")

	def _startMenuReturnSilenceWindow(self):
		if self._menuReturnSilence:
			self._menuReturnSilence["deadline"] = time.monotonic() + _MENU_RETURN_SILENCE_WINDOW

	def _dropMenuReturnSpeech(self, speechSequence):
		state = self._menuReturnSilence
		if time.monotonic() > state["deadline"]:
			self._menuReturnSilence = None
			return speechSequence
		strings = [item for item in speechSequence if isinstance(item, str)]
		if not strings:
			return speechSequence
		isTitle = strings[0].startswith(state["title"])
		isListLabel = state["listLabel"] in [text.replace("&", "") for text in strings]
		if not (isTitle or isListLabel):
			# Our own messages ("Download URL copied") and the list item are spoken as usual
			return speechSequence
		if isListLabel:
			# The list label is the last part of the re-announcement
			self._menuReturnSilence = None
		return [item for item in speechSequence if not isinstance(item, str)]

	def _filterOpenSpeech(self, speechSequence):
		# Rewrites only the first speech after the store opens: the dialog title plus the details of
		# whichever add-on was selected, then the list label. The first list item is left untouched.
		if self._menuReturnSilence:
			return self._dropMenuReturnSpeech(speechSequence)
		state = self._openSpeech
		if not state:
			return speechSequence
		if time.monotonic() > state["deadline"]:
			self._openSpeech = None
			return speechSequence
		strings = [item for item in speechSequence if isinstance(item, str)]
		if not strings:
			return speechSequence
		isTitle = strings[0].startswith(state["title"])
		isListLabel = state["listLabel"] in [text.replace("&", "") for text in strings]
		if not (isTitle or isListLabel):
			self._openSpeech = None
			return speechSequence
		replacement = None
		if not state["announced"]:
			replacement = state["announcement"]
			state["announced"] = True
		filtered = []
		for item in speechSequence:
			if not isinstance(item, str):
				filtered.append(item)
			elif replacement:
				filtered.append(replacement)
				replacement = None
		return filtered

	def event_foreground(self, obj, nextHandler):
		"""
		Monitors top-level window changes to wake up or put the plugin to sleep.
		This prevents expensive tree climbing on every focus change across the OS.
		"""
		self._updateStoreActiveState(obj)
		nextHandler()

	def _updateStoreActiveState(self, foregroundObj):
		self._isStoreActive = False

		try:
			if not foregroundObj or not foregroundObj.appModule:
				return

			# The Add-on Store is an internal NVDA dialog
			if foregroundObj.appModule.appModuleName != "nvda":
				return

			if foregroundObj.role != controlTypes.Role.DIALOG:
				return

			windowTitle = foregroundObj.windowText or foregroundObj.name or ""
			if not windowTitle:
				return

			# Translators: Title of the Add-on Store dialog to match
			storeTitleExact = _("Add-on Store")
			# Translators: Part of the title to match as fallback
			storeTitleFallback1 = _("Store")
			storeTitleFallback2 = _("Add-on")

			if storeTitleExact in windowTitle or storeTitleFallback1 in windowTitle or storeTitleFallback2 in windowTitle:
				self._isStoreActive = True
				logHandler.log.debug("addonStoreLite: Waking up, Add-on Store dialog is active.")

		except (RuntimeError, COMError, AttributeError) as e:
			logHandler.log.debug(f"addonStoreLite: Failed to check foreground state: {e}")

	def event_gainFocus(self, obj, nextHandler):
		# Early Exit 1: If store is not active, sleep immediately (O(1) execution)
		if not getattr(self, "_isStoreActive", False):
			return nextHandler()

		# Early Exit 2: Only target list items
		if not obj or obj.role != controlTypes.Role.LISTITEM:
			return nextHandler()

		# Early Exit 2b: The user turned abbreviations off in the settings panel
		if not storeSettings.get()["abbreviate"]:
			return nextHandler()

		# Early Exit 3: Ensure focus is strictly inside NVDA
		try:
			if not obj.appModule or obj.appModule.appModuleName != "nvda":
				return nextHandler()
		except (RuntimeError, COMError):
			return nextHandler()

		# Process the list item safely
		try:
			originalName = obj.name
			if not originalName:
				return nextHandler()

			condensedName = self._condenseAddonText(originalName)
			if condensedName and condensedName != originalName:
				# Use try...finally to absolutely guarantee original state restoration
				# even if nextHandler() throws an exception from another add-on.
				try:
					obj.name = condensedName
					nextHandler()
				finally:
					obj.name = originalName
				return

		except (RuntimeError, COMError, ValueError) as e:
			logHandler.log.debug(f"addonStoreLite: Exception modifying list item name: {e}")

		nextHandler()

	def _condenseAddonText(self, rawText):
		# Separate trailing " X of Y"
		itemCountMatch = _itemCountPattern.search(rawText)
		if itemCountMatch:
			itemCountSuffix = itemCountMatch.group(1)
			cleanText = rawText[:itemCountMatch.start()].strip()
		else:
			itemCountSuffix = ''
			cleanText = rawText.strip()

		parsedFields = self._parse_fields(cleanText)
		if not parsedFields:
			return None

		addonName = parsedFields.get('name', '')
		addonStatus = parsedFields.get('status', '')
		addonVersion = parsedFields.get('version', '')
		addonAuthor = parsedFields.get('author', '')
		addonDate = parsedFields.get('date', '')

		if not addonName or not addonVersion or not addonAuthor or not addonDate:
			logHandler.log.debug("addonStoreLite: Missing essential fields, using original text.")
			return None

		# Clean author: remove email addresses and extra spaces
		cleanAuthorName = re.sub(r'<[^>]+>', '', addonAuthor)
		cleanAuthorName = re.sub(r'\s+', ' ', cleanAuthorName).strip()

		disableLabel = ""
		# Translators: Word to detect in the status field
		if _('disabled').lower() in addonStatus.lower():
			# Translators: Label for a disabled add-on
			disableLabel = _("Disable")
		condensedResult = displayFormats.buildItemText(
			storeSettings.get()["format"], addonName, addonVersion, cleanAuthorName, addonDate, disableLabel,
		)

		if itemCountSuffix:
			condensedResult += itemCountSuffix

		condensedResult = re.sub(r'\s+', ' ', condensedResult).strip()
		return condensedResult

	def _parse_fields(self, rawText):
		"""
		Parse add-on store item text, handling labeled and positional formats.
		Returns dict with keys: name, status, version, author, date.
		"""
		dataParts = [part.strip() for part in rawText.split(';')]
		if not dataParts:
			return None

		addonName = dataParts[0]

		# Check if labeled format (any part after first contains ':')
		if any(':' in part for part in dataParts[1:]):
			return self._parse_labeled(dataParts, addonName)
		else:
			return self._parse_positional(dataParts, addonName)

	def _parse_labeled(self, dataParts, addonName):
		extractedFields = {'name': addonName}
		for part in dataParts[1:]:
			if ':' not in part:
				continue

			keyRaw, valueRaw = part.split(':', 1)
			targetKey = keyRaw.strip().lower()
			targetValue = valueRaw.strip()

			# Mapping labels to common keys
			# Translators: Label for status in the Add-on Store
			labelStatus = _('status').lower()
			# Translators: Label for installed version
			labelInstVer = _('installed version').lower()
			# Translators: Label for available version
			labelAvailVer = _('available version').lower()
			# Translators: Label for author
			labelAuthor = _('author').lower()
			# Translators: Label for publisher
			labelPublisher = _('publisher').lower()
			# Translators: Label for install date
			labelInstDate = _('install date').lower()
			# Translators: Label for publication date
			labelPubDate = _('publication date').lower()

			if targetKey in (labelStatus, labelInstVer, labelAvailVer, labelAuthor, labelPublisher, labelInstDate, labelPubDate):
				if targetKey in (labelInstVer, labelAvailVer):
					extractedFields['version'] = targetValue
				elif targetKey in (labelAuthor, labelPublisher):
					extractedFields['author'] = targetValue
				elif targetKey in (labelInstDate, labelPubDate):
					extractedFields['date'] = targetValue
				elif targetKey == labelStatus:
					extractedFields['status'] = targetValue

		requiredKeys = ('status', 'version', 'author', 'date')
		if all(k in extractedFields for k in requiredKeys):
			return extractedFields
		return None

	def _parse_positional(self, dataParts, addonName):
		if len(dataParts) < 5:
			return None

		addonStatus = dataParts[1]
		addonVersion = dataParts[2]
		addonAuthor = dataParts[4]

		remainingString = ';'.join(dataParts[5:])
		dateRegexPattern = re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b')
		matchedDates = dateRegexPattern.findall(remainingString)

		if not matchedDates:
			return None

		addonDate = matchedDates[-1]

		return {
			'name': addonName,
			'status': addonStatus,
			'version': addonVersion,
			'author': addonAuthor,
			'date': addonDate
		}
