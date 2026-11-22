# addonStoreLite

Make the NVDA Add-on Store quicker to use: short list items, a short opening announcement, a store that remembers where you were, and a Download command for add-on files.

- **Author:** Chai Chaimee
- **URL:** https://github.com/chaichaimee/addonStoreLite

## Introduction

The Add-on Store reads a lot every time you move through its lists. addonStoreLite shortens what is spoken, remembers your choices, and adds a way to save an add-on file without installing it.

This add-on has no hot keys. It works by itself whenever you open the Add-on Store from NVDA, and its options are in NVDA's Settings dialog under **Add-on Store Lite**.

## Features

### Short List Items

Each item in the Add-on Store lists is read in a short form: name, version, author and date. The e-mail address that some authors add to their name is left out. NVDA's item position, such as "3 of 20", is kept at the end. An add-on that is turned off is marked with the word Disable. If an item does not contain all four details, NVDA reads it in its normal way.

You can choose how the item is spoken in the settings panel. There are five item display formats:

- **Abbreviated: name, version, author, date**: the default.
- **Name, version and date**
- **Name, version and author**
- **Name and version only**
- **Full wording: name, version, by author, date**: spoken as a sentence, for example "name, version 1.0, by author, date".

### Shorter Opening Announcement

When the Add-on Store opens, NVDA normally reads the dialog title, the details of the selected add-on and the list label. With this add-on, the opening announcement is replaced by the name of the tab, followed by "tab selected". This applies only to the first speech after the store opens. The first list item is read as usual.

In the same way, when you close the context menu of an add-on, by pressing Escape or by choosing a command, NVDA does not read the dialog title and the list label again.

### The Store Remembers Where You Were

The next time you open the Add-on Store, it comes back the way you left it:

- **Last tab**: the store opens on the tab you used last: Installed add-ons, Updatable add-ons, Available add-ons or Incompatible add-ons. If NVDA asks for a particular tab, for example Updatable add-ons from the update notification, that tab is used instead.
- **Sort order**: the sort field and its direction are remembered separately for each tab, whether you change them in the sort list or by clicking a column heading. Relevance, which exists only while searching, is not remembered.
- **Channel filter**: remembered for each tab. The External channel is only offered on the Installed and Incompatible tabs.
- **Enabled/disabled filter**: remembered for each tab, except on the Available and Updatable tabs, which do not have it.

The add-on also prevents the errors that could appear when you switch tabs while the sort field is one that the new tab does not show, such as the install date on the Available tab.

### Download and Copy Download URL

On the **Available add-ons** and **Updatable add-ons** tabs, open the context menu of an add-on with the Applications key or Shift+F10. Two commands are added just after the first item of the menu:

- **Download** (Alt+D): saves the add-on file to your download destination without installing it. The label also shows the size of the file, for example "Download 1.56 MB", as soon as it is known.
- **Copy download URL** (Alt+U): copies the address of the add-on file to the clipboard. NVDA says "Download URL copied".

The two commands appear only when a single add-on is selected and the store gives a secure (https) download address for it. They are not added to the menu that appears when several add-ons are selected.

**How a download works**

1. NVDA says "Downloading" followed by the add-on name. The download runs in the background, so you can keep working.
2. The file is saved with the name given in its address. If that name is not usable, it is named with the add-on id and version, ending in `.nvda-addon`.
3. When the file has been saved completely, a short high tone is played.

While the file is being received, it has the extra ending `.part`, and this temporary file is removed if the download fails. The file is compared with the checksum published by the store, and it is rejected if they do not match. A file larger than 256 MB is refused. Only one download can run at a time; if you start another, NVDA says "A download is already in progress".

When something goes wrong, NVDA says one of these: "Download failed", "Download failed: the file is too large", "Download failed: the file was empty" or "Download failed: the file did not match its checksum". If the add-on has no download address, NVDA says "This add-on has no download address". If the address cannot be copied, NVDA says "Could not copy the download URL".

> **Privacy:** opening the context menu makes one small request to the add-on's download address, only to read the size of the file. The request asks for a single byte, and it is made once for each add-on version. The size is then remembered in a file, so the next time it is shown without any request. If the size cannot be read, no new try is made for the same address for five minutes. The file itself is fetched only when you choose Download.

### Settings Panel

Open NVDA's Settings dialog (NVDA+Control+G) and choose the category **Add-on Store Lite**. The panel has these controls:

- **Show abbreviations for items in the Add-on Store** (Alt+A): a check box that turns the short list items on or off. It is on by default. When it is off, the list items are read in NVDA's normal way and the format list is disabled.
- **Item display format** (Alt+F): the list of the five formats described above. The default is Abbreviated.
- **Download destination (empty uses your Downloads folder)**: the full path of the folder where downloaded add-ons are saved. If you leave it empty, the Windows Downloads folder is used. If Windows cannot give that folder, a folder named downloads inside the add-on's settings folder is used. The folder is created if it does not exist.
- **Browse** (Alt+B): opens a dialog to choose the destination folder.

The download destination must be a full folder path. If it is not, NVDA says "The download destination must be a full folder path and was not changed" and the previous folder is kept. If the settings cannot be written, NVDA says "Add-on Store Lite settings could not be saved".

### Where the Settings Are Kept

The add-on keeps its files in a folder named `ChaiChaimee\addonStoreLite` inside the NVDA configuration folder:

- `settings.json`: the options of the settings panel.
- `storeState.json`: the last tab, and the sort order and filters of each tab.
- `addonSizes.json`: the remembered file sizes of add-ons.

Files are saved safely, with a backup copy ending in `.bak`, so a power cut cannot leave a file half written. If a file cannot be read, its backup is used, and if that fails too, the default values are used.

The add-on does nothing on NVDA's secure screens, such as the sign-in screen.

## Support Me

If this tool has made your life easier, consider fueling the next update with a small donation.

[![Support me](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01)

Your support means the world. Let's build something great together

&copy; 2026 Chai Chaimee NVDA Add-on Released under GNU GPL
