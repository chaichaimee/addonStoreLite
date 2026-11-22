# displayFormats.py

import re

import addonHandler

addonHandler.initTranslation()

DEFAULT_FORMAT = "abbreviated"


def _abbreviated(name, version, author, date, disabledLabel):
	return " ".join(part for part in (name, version, disabledLabel, author, date) if part)


def _nameVersionDate(name, version, author, date, disabledLabel):
	return " ".join(part for part in (name, version, disabledLabel, date) if part)


def _nameVersionAuthor(name, version, author, date, disabledLabel):
	return " ".join(part for part in (name, version, disabledLabel, author) if part)


def _nameVersion(name, version, author, date, disabledLabel):
	return " ".join(part for part in (name, version, disabledLabel) if part)


def _sentence(name, version, author, date, disabledLabel):
	# Translators: Spoken form of an add-on list item; {name}, {version}, {author} and {date} are replaced by the add-on's values
	text = _("{name}, version {version}, by {author}, {date}").format(
		name=name, version=version, author=author, date=date,
	)
	if disabledLabel:
		text = f"{text}, {disabledLabel}"
	return text


def getFormatChoices():
	"""Returns (key, label) pairs in the order shown in the settings panel; the first one is the default."""
	return [
		# Translators: Item display format in the settings panel
		("abbreviated", _("Abbreviated: name, version, author, date")),
		# Translators: Item display format in the settings panel
		("nameVersionDate", _("Name, version and date")),
		# Translators: Item display format in the settings panel
		("nameVersionAuthor", _("Name, version and author")),
		# Translators: Item display format in the settings panel
		("nameVersion", _("Name and version only")),
		# Translators: Item display format in the settings panel
		("sentence", _("Full wording: name, version, by author, date")),
	]


_BUILDERS = {
	"abbreviated": _abbreviated,
	"nameVersionDate": _nameVersionDate,
	"nameVersionAuthor": _nameVersionAuthor,
	"nameVersion": _nameVersion,
	"sentence": _sentence,
}


def isKnownFormat(formatKey):
	return formatKey in _BUILDERS


def buildItemText(formatKey, name, version, author, date, disabledLabel=""):
	builder = _BUILDERS.get(formatKey, _abbreviated)
	return re.sub(r"\s+", " ", builder(name, version, author, date, disabledLabel)).strip()
