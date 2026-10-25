# settingsPanel.py

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

	def _onAbbreviateToggle(self, evt):
		self.formatChoice.Enable(self.abbreviateCheck.GetValue())

	def onSave(self):
		selection = self.formatChoice.GetSelection()
		if selection == wx.NOT_FOUND:
			selection = 0
		if not storeSettings.save(self.abbreviateCheck.GetValue(), self.formatKeys[selection]):
			# Translators: Spoken when the settings file could not be written
			ui.message(_("Add-on Store Lite settings could not be saved"))
