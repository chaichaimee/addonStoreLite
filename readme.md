# Add-on Store Lite

Say goodbye to information overload in the NVDA Add-on Store.

- **Author:** Chai Chaimee
- **URL:** https://github.com/chaichaimee/addonStoreLite
- **NVDA compatibility:** 2025.1 to 2026.3
- **License:** GNU GPL

## Introduction

Out of the box, every item in NVDA's Add-on Store is read with a long string of details. Add-on Store Lite shortens what NVDA says for each item, so you hear the facts you need as you arrow through the list. It also shortens the announcement that plays when the store opens, and it remembers your tab, sort order and filters.

There are no hotkeys and nothing to start. Install it, open the Add-on Store, and it works. Options are in NVDA Settings, in the **Add-on Store Lite** category.

## Features

### Short spoken list items

When focus lands on an add-on in the list, the long spoken text is replaced with a short one: name, version, author and date. The e-mail address is removed from the author's name, NVDA's own position text (for example "3 of 20") stays at the end, and a disabled add-on is marked with the word Disable.

If an item lacks any of the needed details (name, version, author, date), NVDA reads it in its original form. Only speech changes; the text on screen is untouched. It works on the Installed, Updatable, Available and Incompatible tabs.

### Item display format

| Format | Spoken as |
| --- | --- |
| Abbreviated: name, version, author, date (default) | `Sample Add-on 1.2.0 Chai Chaimee 10/05/2026` |
| Name, version and date | `Sample Add-on 1.2.0 10/05/2026` |
| Name and version only | `Sample Add-on 1.2.0` |
| Full wording: name, version, by author, date | `Sample Add-on, version 1.2.0, by Chai Chaimee, 10/05/2026` |

For a disabled add-on, Disable is added after the version (or at the end in the full wording format).

### Shorter opening announcement

When the store opens, the first announcement is shortened to the open tab's name, "tab", "selected", and then the list label. Only the first announcement within a few seconds of opening is changed; the first list item is read normally.

### The store remembers your choices

Each tab keeps its own settings, restored the next time the store opens:

- **Last tab.** The store opens on the tab you used last. A tab requested by NVDA itself (for example from the updates notification) takes priority.
- **Sort order.** Field and direction, whether changed in the sort list or by clicking a column heading. The Relevance sort (search only) is not saved.
- **Channel filter.** The External channel is only restored on tabs that offer it.
- **Enabled / Disabled filter.** Remembered on the Installed and Incompatible tabs.

The search box is not remembered.

### Smooth tab switching on new NVDA versions

NVDA 2026.2 and later keep the sort field across tabs, and a field that is hidden on the next tab (such as install date on Available) could make the switch fail. Add-on Store Lite switches to a safe sort field before the tab changes.

### Fast and safe

The add-on only works while the Add-on Store is in the foreground and exits immediately everywhere else, so NVDA is not slowed down or frozen. Everything it changes in NVDA is restored when the add-on is disabled or NVDA closes. On secure screens it does nothing.

## Settings

Open NVDA Settings (`NVDA+Control+G`) and choose **Add-on Store Lite**.

1. **Show abbreviations for items in the Add-on Store**: checked by default. Uncheck it to hear NVDA's original text for every item.
2. **Item display format**: choose one of the four formats. Unavailable while abbreviations are off.
3. Press OK or Apply.

If saving fails, NVDA says "Add-on Store Lite settings could not be saved".

## Where your data is kept

Two files are stored in `ChaiChaimee\addonStoreLite` inside the NVDA configuration folder in use (installed, portable or custom path):

- `settings.json`: the check box and the display format.
- `storeState.json`: the last tab, sort orders and filters.

Files are written safely with a `.bak` backup. If a file is damaged, the backup, then the defaults, are used. Deleting the folder resets everything.

## Requirements

NVDA 2025.1 or later. Last tested with NVDA 2026.3.

## Support me

If this tool has made your life easier, consider fueling the next update with a small donation.

[![Support me](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01)

Your support means the world. Let's build something great together.

&copy; 2026 Chai Chaimee. NVDA add-on released under GNU GPL.
