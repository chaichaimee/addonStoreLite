# settingsPanel.py

import os

import addonHandler
import ui
import wx
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel

from . import displayFormats, storeSettings

addonHandler.initTranslation()


class AddonStoreLiteSettingsPanel(SettingsPanel):
	# Translators: Title of the settings category for this add-on
	title = _("Add-on Store Lite")

	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		current = storeSettings.get()

		# Translators: Check box in the settings panel
		self.abbreviateCheck = sHelper.addItem(wx.CheckBox(self, label=_("Show &abbreviations for items in the Add-on Store")))
		self.abbreviateCheck.SetValue(current["abbreviate"])
		self.abbreviateCheck.Bind(wx.EVT_CHECKBOX, self._onAbbreviateToggle)

		self.formatKeys = []
		formatLabels = []
		for key, label in displayFormats.getFormatChoices():
			self.formatKeys.append(key)
			formatLabels.append(label)
		# Translators: Label of the combo box that selects how add-on list items are spoken
		self.formatChoice = sHelper.addLabeledControl(_("Item display &format:"), wx.Choice, choices=formatLabels)
		self.formatChoice.SetSelection(self.formatKeys.index(current["format"]))
		self.formatChoice.Enable(current["abbreviate"])

		# Translators: Label of the edit field that holds the folder where downloaded add-ons are saved
		self.downloadFolderEdit = sHelper.addLabeledControl(_("Download destination (empty uses your Downloads folder):"), wx.TextCtrl)
		self.downloadFolderEdit.SetValue(current["downloadFolder"])
		# Translators: Button that opens a dialog to browse for the download destination folder
		self.browseButton = sHelper.addItem(wx.Button(self, label=_("&Browse...")))
		self.browseButton.Bind(wx.EVT_BUTTON, self._onBrowse)

	def _onAbbreviateToggle(self, evt):
		self.formatChoice.Enable(self.abbreviateCheck.GetValue())

	def _onBrowse(self, evt):
		startFolder = self.downloadFolderEdit.GetValue().strip()
		if not os.path.isdir(startFolder):
			startFolder = ""
		# Translators: Title of the dialog used to browse for the download destination folder
		with wx.DirDialog(self, _("Choose the download destination"), defaultPath=startFolder) as folderDialog:
			if folderDialog.ShowModal() == wx.ID_OK:
				self.downloadFolderEdit.SetValue(folderDialog.GetPath())

	def onSave(self):
		selection = self.formatChoice.GetSelection()
		if selection == wx.NOT_FOUND:
			selection = 0
		downloadFolder = self.downloadFolderEdit.GetValue().strip()
		if downloadFolder and not os.path.isabs(downloadFolder):
			# Translators: Spoken when the download destination is not a full folder path; the previous one is kept
			ui.message(_("The download destination must be a full folder path and was not changed"))
			downloadFolder = storeSettings.get()["downloadFolder"]
			self.downloadFolderEdit.SetValue(downloadFolder)
		if not storeSettings.save(self.abbreviateCheck.GetValue(), self.formatKeys[selection], downloadFolder):
			# Translators: Spoken when the settings file could not be written
			ui.message(_("Add-on Store Lite settings could not be saved"))
