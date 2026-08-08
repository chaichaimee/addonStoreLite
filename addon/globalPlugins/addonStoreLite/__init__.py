# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import os
import sys
import threading
import addonHandler
import core
import logHandler

addonHandler.initTranslation()

import re
import globalPluginHandler
import controlTypes
import api
try:
	from comtypes import COMError
except ImportError:
	COMError = Exception

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	
	def __init__(self):
		super(GlobalPlugin, self).__init__()
		# State toggle acting as a watchdog sleep/wake mechanism
		self._isStoreActive = False
		# Translators: Log message when the add-on is loaded
		logHandler.log.info(_("addonStoreLite loaded"))

	def terminate(self):
		# Strict cleanup to prevent zombie state
		self._isStoreActive = False
		super(GlobalPlugin, self).terminate()

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
				
			if foregroundObj.role != controlTypes.ROLE_DIALOG:
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
		if not obj or obj.role != controlTypes.ROLE_LISTITEM:
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
		# Translators: Regular expression to match 'X of Y' item count (maintain the 'of' logic)
		itemCountMatch = re.search(_(r'(\s+\d+\s+of\s+\d+)$'), rawText)
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

		# Add " Disable" only if status contains "Disabled" (case-insensitive)
		# Translators: Word to detect in the status field
		if _('disabled').lower() in addonStatus.lower():
			# Translators: Label for a disabled add-on
			disableLabel = _("Disable")
			baseString = f"{addonName} {addonVersion} {disableLabel}"
			condensedResult = f"{baseString}  {cleanAuthorName} {addonDate}"
		else:
			condensedResult = f"{addonName} {addonVersion} {cleanAuthorName} {addonDate}"

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