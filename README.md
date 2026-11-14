# Aeronist PDF Editor

A small desktop tool for merging PDF files and images and rearranging their pages.
Built with PySide6 (Qt 6) and pypdf; runs on Linux and Windows.
The user interface is in Turkish.

## Features

- Merge several PDFs into a single document
- Add images as pages: PNG, JPG/JPEG, BMP, GIF, TIFF (multi-page), WebP
- Reorder pages with drag & drop (multi-selection supported)
- Move pages left/right, to the start/end; reverse the page order
- Delete pages
- Reorder whole files in the side panel; pages are regrouped by file order
- Undo / redo
- Password-protected PDFs
- Large page preview (double-click a page)

Page contents are never modified: pages are copied as they are into the output file.

## Running from source

```bash
python -m venv .venv
# Linux:   source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python aeronist_pdf_editor.py
```

Files can also be passed on the command line:

```bash
python aeronist_pdf_editor.py report.pdf scan.jpg appendix.pdf
```

The `assets/` folder (logo and icons) must stay next to the script.

> **Linux note:** Qt 6.5+ needs the `libxcb-cursor0` package.
> If the app does not start: `sudo apt install libxcb-cursor0`

## Usage

| Action | How |
|---|---|
| Add files | **Dosya Ekle** (Ctrl+O), or drag files onto the window. Dropping onto the page grid inserts the pages at that position. |
| Reorder pages | Drag & drop (Ctrl/Shift or a rubber band for multi-selection), or **Sola / Sağa** (Ctrl+←/→) and **Başa / Sona** (Ctrl+Home/End). |
| Delete pages | Select and press **Delete**. |
| Reverse | **Ters Çevir** reverses the selected pages, or the whole document if nothing is selected. |
| File order | Drag files in the side panel or use the ▲/▼ buttons. |
| Select a file's pages | Double-click the file in the side panel. |
| Preview | Double-click a page; navigate with ←/→. |
| Undo / redo | Ctrl+Z / Ctrl+Y |
| Save | **Kaydet** (Ctrl+S). The suggested name is `pdf_HH-MM-SS_DD-MM-YYYY.pdf` (time and date of saving). |

### How images are placed

Each image becomes an A4 page, in portrait or landscape to match the image.
Large images are scaled down to fit the page; small images keep their natural size
(based on their DPI) and are centered, so they are not enlarged and pixelated.
EXIF rotation of phone photos is applied, and transparent areas become white.

## Building standalone binaries (optional)

Install PyInstaller in the same environment:

```bash
pip install pyinstaller
```

**Windows (.exe)**

```bat
pyinstaller --onefile --windowed --name Aeronist_PDF_Editor ^
  --icon assets\app-icon.ico --add-data "assets;assets" aeronist_pdf_editor.py
```

**Linux**

```bash
pyinstaller --windowed --name aeronist-pdf-editor \
  --add-data "assets:assets" aeronist_pdf_editor.py
```

The result is written to `dist/`. Build the Windows binary on Windows and the
Linux binary on Linux. To produce an AppImage, place the Linux build in an AppDir
and package it with [appimagetool](https://github.com/AppImage/appimagetool).

## Project layout

```
aeronist_pdf_editor.py   application (single file)
assets/
  app-icon.png / .ico    application icon
  logo-white.png         logo for the dark header
  logo-dark.png          logo for light backgrounds (empty state)
requirements.txt
```
