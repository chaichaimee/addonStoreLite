# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import re
import globalPluginHandler
import controlTypes
from logHandler import log
import addonHandler

# Initialize translation
addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        # Translators: Log message when the add-on is loaded
        log.info(_("addonStoreLite loaded"))

    def event_gainFocus(self, obj, nextHandler):
        if self._isAddonStoreListItem(obj):
            original = obj.name
            if original:
                modified = self._condenseAddonText(original)
                if modified and modified != original:
                    obj.name = modified
                    nextHandler()
                    obj.name = original
                    return
        nextHandler()

    def _isAddonStoreListItem(self, obj):
        if obj.role != controlTypes.ROLE_LISTITEM:
            return False
        parent = obj.parent
        while parent and parent.role != controlTypes.ROLE_DIALOG:
            parent = parent.parent
        # Translators: Title of the Add-on Store dialog to match
        if parent and parent.windowText and _("Add-on Store") in parent.windowText:
            return True
        # Fallback for possible localized or slightly different titles
        # Translators: Part of the title to match as fallback
        if parent and parent.windowText and (_("Store") in parent.windowText or _("Add-on") in parent.windowText):
            return True
        return False

    def _condenseAddonText(self, rawText):
        # Separate trailing " X of Y"
        # Translators: Regular expression to match 'X of Y' item count (maintain the 'of' logic)
        m = re.search(_(r'(\s+\d+\s+of\s+\d+)$'), rawText)
        if m:
            item_count = m.group(1)
            text = rawText[:m.start()].strip()
        else:
            item_count = ''
            text = rawText.strip()

        fields = self._parse_fields(text)
        if not fields:
            return None

        name = fields.get('name', '')
        status = fields.get('status', '')
        version = fields.get('version', '')
        author = fields.get('author', '')
        date = fields.get('date', '')

        if not name or not version or not author or not date:
            log.debug("Missing essential fields, using original")
            return None

        # Clean author: remove email addresses and extra spaces
        author_clean = re.sub(r'<[^>]+>', '', author)
        author_clean = re.sub(r'\s+', ' ', author_clean).strip()

        # Add " Disable" only if status contains "Disabled" (case-insensitive)
        # Translators: Word to detect in the status field
        if _('disabled').lower() in status.lower():
            # Translators: Label for a disabled add-on
            disable_label = _("Disable")
            base = f"{name} {version} {disable_label}"
            condensed = f"{base}  {author_clean} {date}"
        else:
            condensed = f"{name} {version} {author_clean} {date}"

        if item_count:
            condensed += item_count

        condensed = re.sub(r'\s+', ' ', condensed).strip()
        return condensed

    def _parse_fields(self, text):
        """
        Parse add-on store item text, handling labeled and positional formats.
        Returns dict with keys: name, status, version, author, date.
        """
        parts = [p.strip() for p in text.split(';')]
        if not parts:
            return None

        name = parts[0]

        # Check if labeled format (any part after first contains ':')
        if any(':' in p for p in parts[1:]):
            return self._parse_labeled(parts, name)
        else:
            return self._parse_positional(parts, name)

    def _parse_labeled(self, parts, name):
        fields = {'name': name}
        for part in parts[1:]:
            if ':' not in part:
                continue
            key, value = part.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            # Mapping labels to common keys
            # Translators: Label for status in the Add-on Store
            label_status = _('status').lower()
            # Translators: Label for installed version
            label_inst_ver = _('installed version').lower()
            # Translators: Label for available version
            label_avail_ver = _('available version').lower()
            # Translators: Label for author
            label_author = _('author').lower()
            # Translators: Label for publisher
            label_publisher = _('publisher').lower()
            # Translators: Label for install date
            label_inst_date = _('install date').lower()
            # Translators: Label for publication date
            label_pub_date = _('publication date').lower()

            if key in (label_status, label_inst_ver, label_avail_ver, label_author, label_publisher, label_inst_date, label_pub_date):
                if key in (label_inst_ver, label_avail_ver):
                    fields['version'] = value
                elif key in (label_author, label_publisher):
                    fields['author'] = value
                elif key in (label_inst_date, label_pub_date):
                    fields['date'] = value
                elif key == label_status:
                    fields['status'] = value
        
        required = ('status', 'version', 'author', 'date')
        if all(k in fields for k in required):
            return fields
        return None

    def _parse_positional(self, parts, name):
        if len(parts) < 5:
            return None

        status = parts[1]
        version = parts[2]
        author = parts[4]

        remaining = ';'.join(parts[5:])
        date_pattern = re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b')
        dates = date_pattern.findall(remaining)
        if not dates:
            return None
        date = dates[-1]

        return {
            'name': name,
            'status': status,
            'version': version,
            'author': author,
            'date': date
        }