#!/usr/bin/env python3
"""
Aeronist PDF Editor — merge PDFs/images and rearrange pages.

Features:
  * Merge several PDF files into one document
  * Add images (PNG, JPG, BMP, GIF, TIFF, WebP) as pages
  * Reorder pages with drag & drop, move them left/right/to start/to end
  * Delete pages, reverse page order
  * Reorder whole files from the side panel (pages are regrouped by file)
  * Undo / redo
  * Password-protected PDFs
  * Large page preview (double-click)

Requirements: PySide6, pypdf (see requirements.txt). Runs on Linux and Windows.
The user interface is in Turkish.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QItemSelectionModel,
    QMarginsF,
    QMimeData,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QDrag,
    QFont,
    QIcon,
    QImage,
    QImageReader,
    QKeySequence,
    QPageLayout,
    QPageSize,
    QPainter,
    QPalette,
    QPdfWriter,
    QPen,
    QPixmap,
)
from PySide6.QtPdf import QPdfDocument
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProxyStyle,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStyle,
    QStyleFactory,
    QStyledItemDelegate,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Aeronist PDF Editor"
APP_ID = "aeronist-pdf-editor"
PAGE_MIME = "application/x-aeronist-pdf-editor-pages"
ROLE_REF = Qt.UserRole + 1
ROLE_DOC = Qt.UserRole + 2
ROLE_INFO = Qt.UserRole + 3

PDF_EXTS = (".pdf",)
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp")
SUPPORTED_EXTS = PDF_EXTS + IMAGE_EXTS

# --------------------------------------------------------------------------- #
#  Theme
# --------------------------------------------------------------------------- #
C_HEADER = "#0f172a"        # header bar (slate-900)
C_BG = "#f4f6fa"            # window background
C_SURFACE = "#ffffff"       # panels
C_CANVAS = "#e9edf3"        # page grid background
C_BORDER = "#e2e8f0"
C_TEXT = "#0f172a"
C_MUTED = "#64748b"
C_ACCENT = "#2563eb"
C_ACCENT_HOVER = "#1d4ed8"
C_ACCENT_SOFT = "#dbe7ff"

# Each source file gets its own color (shown as a dot next to its pages),
# so it is easy to see where a page came from.
DOC_COLORS = [
    "#2563eb", "#e0533d", "#16a34a", "#9333ea", "#e69b00",
    "#0891b2", "#db2777", "#64748b", "#a16207", "#4f46e5",
]

STYLESHEET = f"""
QMainWindow, QDialog {{ background: {C_BG}; }}
QWidget {{ color: {C_TEXT}; }}

QFrame#header {{ background: {C_HEADER}; }}
QFrame#header QToolBar {{ background: transparent; border: none; spacing: 2px; padding: 0; }}
QFrame#header QToolBar::separator {{
    background: rgba(255, 255, 255, 0.12);
    width: 1px;
    margin: 10px 8px;
}}
QFrame#headerLine {{ background: rgba(255, 255, 255, 0.12); }}
QFrame#header QToolButton {{
    color: #e2e8f0;
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 8px 8px;
    min-width: 50px;
}}
QFrame#header QToolButton#qt_toolbar_ext_button {{
    min-width: 0; padding: 0; border-radius: 8px;
}}
QFrame#header QToolButton:hover {{ background: rgba(255, 255, 255, 0.09); }}
QFrame#header QToolButton:pressed {{ background: rgba(255, 255, 255, 0.16); }}
QFrame#header QToolButton:disabled {{ color: #5b6b82; }}
QFrame#header QToolButton#primary {{
    background: {C_ACCENT};
    color: white;
    font-weight: 600;
    padding: 11px 22px;
    border-radius: 10px;
}}
QFrame#header QToolButton#primary:hover {{ background: {C_ACCENT_HOVER}; }}
QFrame#header QToolButton#primary:disabled {{ background: #334155; color: #7b8aa0; }}
QFrame#header QLabel {{ color: #94a3b8; background: transparent; }}
QFrame#header QSlider {{ background: transparent; }}
QFrame#header QSlider::groove:horizontal {{
    height: 4px; background: rgba(255, 255, 255, 0.18); border-radius: 2px;
}}
QFrame#header QSlider::sub-page:horizontal {{ background: #60a5fa; border-radius: 2px; }}
QFrame#header QSlider::handle:horizontal {{
    background: white; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}}
QMenu {{ background: {C_SURFACE}; border: 1px solid {C_BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px 6px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background: {C_ACCENT_SOFT}; color: {C_TEXT}; }}
QMenu::item:disabled {{ color: #a0aec0; }}

QFrame#side {{ background: {C_SURFACE}; border-right: 1px solid {C_BORDER}; }}
QLabel#panelTitle {{ font-size: 11pt; font-weight: 600; }}
QLabel#hint {{ color: {C_MUTED}; font-size: 9pt; }}

QListWidget#fileList {{ background: transparent; border: none; outline: 0; }}
QListWidget#fileList::item {{
    padding: 8px 6px; border-radius: 8px; margin: 1px 0; color: {C_TEXT};
}}
QListWidget#fileList::item:hover {{ background: #f1f5f9; }}
QListWidget#fileList::item:selected {{ background: {C_ACCENT_SOFT}; color: {C_TEXT}; }}

QListWidget#pageGrid {{ background: {C_CANVAS}; border: none; outline: 0; }}

QPushButton {{
    background: {C_SURFACE};
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 20px;
}}
QPushButton:hover {{ background: #f1f5f9; border-color: #94a3b8; }}
QPushButton:pressed {{ background: #e2e8f0; }}
QPushButton:disabled {{ color: #a0aec0; border-color: {C_BORDER}; }}
QPushButton:default {{ border-color: {C_ACCENT}; }}

QStatusBar {{ background: {C_SURFACE}; border-top: 1px solid {C_BORDER}; color: {C_MUTED}; }}
QStatusBar QLabel {{ color: {C_MUTED}; padding: 2px 6px; }}
QStatusBar::item {{ border: none; }}

QSplitter::handle {{ background: {C_BORDER}; }}

QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #c3cbd8; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #94a3b8; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #c3cbd8; border-radius: 4px; min-width: 36px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {C_HEADER}; color: white; border: none; padding: 6px 8px;
}}
QLabel#previewArea {{ background: #dfe5ee; border-radius: 10px; }}
"""


class AppStyle(QProxyStyle):
    """Fusion with a wider toolbar overflow ("more") button."""

    def pixelMetric(self, metric, option=None, widget=None):
        if metric == QStyle.PM_ToolBarExtensionExtent:
            return 40
        return super().pixelMetric(metric, option, widget)


def apply_theme(app: QApplication) -> None:
    """Fusion style + fixed light palette, so the app looks the same everywhere."""
    app.setStyle(AppStyle(QStyleFactory.create("Fusion")))
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(C_BG))
    pal.setColor(QPalette.WindowText, QColor(C_TEXT))
    pal.setColor(QPalette.Base, QColor(C_SURFACE))
    pal.setColor(QPalette.AlternateBase, QColor("#f8fafc"))
    pal.setColor(QPalette.Text, QColor(C_TEXT))
    pal.setColor(QPalette.Button, QColor(C_SURFACE))
    pal.setColor(QPalette.ButtonText, QColor(C_TEXT))
    pal.setColor(QPalette.Highlight, QColor(C_ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ToolTipBase, QColor(C_HEADER))
    pal.setColor(QPalette.ToolTipText, QColor("white"))
    pal.setColor(QPalette.PlaceholderText, QColor("#94a3b8"))
    pal.setColor(QPalette.Link, QColor(C_ACCENT))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#a0aec0"))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)


def asset_path(name: str) -> str:
    """Path of a bundled asset (works from source and from a PyInstaller build)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)


# --------------------------------------------------------------------------- #
#  Line icons (SVG, drawn in any color)
# --------------------------------------------------------------------------- #
_SVG_PATHS = {
    "add": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
           '<path d="M14 3v5h5"/><path d="M12 11v6M9 14h6"/>',
    "save": '<path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 20h14"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/>',
    "trash": '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/>'
             '<path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12"/><path d="M9 7V4h6v3"/>',
    "first": '<path d="M6 5v14"/><path d="M18 6l-7 6 7 6"/>',
    "left": '<path d="M15 6l-6 6 6 6"/>',
    "right": '<path d="M9 6l6 6-6 6"/>',
    "last": '<path d="M18 5v14"/><path d="M6 6l7 6-7 6"/>',
    "reverse": '<path d="M7 4L3 8l4 4"/><path d="M3 8h14"/><path d="M17 20l4-4-4-4"/><path d="M21 16H7"/>',
    "select": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8.5 12.5l2.5 2.5 5-6"/>',
    "clear": '<circle cx="12" cy="12" r="8.5"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "up": '<path d="M6 15l6-6 6 6"/>',
    "down": '<path d="M6 9l6 6 6-6"/>',
    "more": '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/>'
            '<circle cx="19" cy="12" r="1.2"/>',
}


def _render_svg(name: str, color: str, size: int, dpr: float) -> QPixmap:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="1.9" stroke-linecap="round" '
           f'stroke-linejoin="round">{_SVG_PATHS[name]}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def line_icon(name: str, color: str, disabled: str, size: int = 24) -> QIcon:
    icon = QIcon()
    for dpr in (1.0, 2.0):
        icon.addPixmap(_render_svg(name, color, size, dpr), QIcon.Normal)
        icon.addPixmap(_render_svg(name, disabled, size, dpr), QIcon.Disabled)
    return icon


# --------------------------------------------------------------------------- #
#  Data model
# --------------------------------------------------------------------------- #
@dataclass
class SourceDoc:
    id: int
    path: str
    name: str
    kind: str                  # "pdf" or "image"
    color: QColor
    reader: PdfReader          # used when saving (pypdf)
    qdoc: QPdfDocument         # used for drawing thumbnails (QtPdf)
    buffer: QBuffer            # in-memory data read by qdoc (must stay alive)
    page_count: int


@dataclass(frozen=True)
class PageRef:
    doc_id: int
    index: int                 # 0-based page number inside the source document


# --------------------------------------------------------------------------- #
#  Image -> PDF conversion
# --------------------------------------------------------------------------- #
def image_to_pdf(path: str) -> bytes:
    """Converts an image file to an in-memory PDF (one page per image frame).

    Pages are A4, oriented like the image. Large images are scaled down to fit
    the page; small images keep their natural size (by their DPI) and are
    centered, so they are not blown up and pixelated. Multi-page TIFFs become
    multiple pages.
    """
    reader = QImageReader(path)
    reader.setAutoTransform(True)              # honour EXIF rotation (phone photos)
    fmt = bytes(reader.format()).lower()
    count = max(1, reader.imageCount()) if fmt in (b"tif", b"tiff") else 1

    frames: list[QImage] = []
    for i in range(count):
        if i > 0 and not reader.jumpToNextImage():
            break
        img = reader.read()
        if img.isNull():
            if not frames:
                raise ValueError(reader.errorString())
            break
        frames.append(img)

    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    writer = QPdfWriter(buf)
    writer.setCreator(APP_NAME)
    writer.setTitle(os.path.basename(path))
    writer.setResolution(300)
    res = writer.resolution()
    painter: QPainter | None = None

    for img in frames:
        if img.hasAlphaChannel():              # flatten transparency onto white
            flat = QImage(img.size(), QImage.Format_RGB32)
            flat.setDotsPerMeterX(img.dotsPerMeterX())
            flat.setDotsPerMeterY(img.dotsPerMeterY())
            flat.fill(Qt.white)
            fp = QPainter(flat)
            fp.drawImage(0, 0, img)
            fp.end()
            img = flat

        orientation = (QPageLayout.Landscape if img.width() > img.height()
                       else QPageLayout.Portrait)
        writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), orientation,
                                         QMarginsF(0, 0, 0, 0)))
        if painter is None:
            painter = QPainter(writer)
        else:
            writer.newPage()

        page = writer.pageLayout().paintRectPixels(res)
        dpi = img.dotsPerMeterX() * 0.0254
        if not 50 <= dpi <= 1200:
            dpi = 96.0
        nat_w = img.width() / dpi * res
        nat_h = img.height() / dpi * res
        scale = min(1.0, page.width() / nat_w, page.height() / nat_h)
        w, h = nat_w * scale, nat_h * scale
        target = QRectF(page.x() + (page.width() - w) / 2,
                        page.y() + (page.height() - h) / 2, w, h)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(target, img)

    if painter is not None:
        painter.end()
    buf.close()
    return bytes(buf.data())


# --------------------------------------------------------------------------- #
#  Rendering helpers
# --------------------------------------------------------------------------- #
def render_page(qdoc: QPdfDocument, index: int, max_w: int, max_h: int,
                dpr: float = 1.0) -> QPixmap:
    """Renders a page to fit in a (max_w x max_h) box, keeping its aspect ratio."""
    size = qdoc.pagePointSize(index)
    w, h = size.width(), size.height()
    if w <= 0 or h <= 0:
        w, h = 595.0, 842.0
    scale = min(max_w / w, max_h / h)
    tw, th = max(1, int(w * scale)), max(1, int(h * scale))
    img = qdoc.render(index, QSize(int(tw * dpr), int(th * dpr)))
    pm = QPixmap(int(tw * dpr), int(th * dpr))
    pm.fill(Qt.white)          # QtPdf renders with a transparent background
    p = QPainter(pm)
    p.drawImage(0, 0, img)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def make_thumbnail(qdoc: QPdfDocument, index: int, box: int, dpr: float) -> QIcon:
    """Square thumbnail: the page centered in the box with a soft drop shadow."""
    pad = 6
    page = render_page(qdoc, index, box - 2 * pad, box - 2 * pad, dpr)
    canvas = QPixmap(int(box * dpr), int(box * dpr))
    canvas.setDevicePixelRatio(dpr)
    canvas.fill(Qt.transparent)
    pw, ph = page.width() / dpr, page.height() / dpr
    x, y = (box - pw) / 2, (box - ph) / 2
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    for i, alpha in enumerate((10, 14, 20, 28)):      # soft shadow
        grow = 4 - i
        p.setBrush(QColor(15, 23, 42, alpha))
        p.drawRoundedRect(QRectF(x - grow, y - grow + 2, pw + 2 * grow, ph + 2 * grow), 3, 3)
    p.drawPixmap(QPoint(int(x), int(y)), page)
    p.setPen(QPen(QColor(15, 23, 42, 40), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(x, y, pw, ph).adjusted(0.5, 0.5, -0.5, -0.5))
    p.end()
    return QIcon(canvas)


def placeholder_icon(box: int) -> QIcon:
    pm = QPixmap(box, box)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    w, h = int(box * 0.66), int(box * 0.92)
    r = QRect((box - w) // 2, (box - h) // 2, w, h)
    p.setPen(QPen(QColor("#cbd5e1"), 1))
    p.setBrush(QColor("#f8fafc"))
    p.drawRoundedRect(r, 3, 3)
    p.setPen(QColor("#94a3b8"))
    p.drawText(r, Qt.AlignCenter, "…")
    p.end()
    return QIcon(pm)


def dot_icon(color: QColor, size: int = 12) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------- #
#  Page grid (custom drag & drop + custom item painting)
# --------------------------------------------------------------------------- #
class PageDelegate(QStyledItemDelegate):
    """Paints a page as a card: thumbnail, position and source file below it."""

    def __init__(self, grid: "PageGrid"):
        super().__init__(grid)
        self.grid = grid

    def sizeHint(self, option, index):
        return self.grid.gridSize()

    def paint(self, p: QPainter, option, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(4, 4, -4, -4)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected:
            p.setPen(QPen(QColor(C_ACCENT), 2))
            p.setBrush(QColor(C_ACCENT_SOFT))
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 10, 10)
        elif hovered:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawRoundedRect(r, 10, 10)

        s = self.grid.iconSize()
        icon = index.data(Qt.DecorationRole)
        top = int(r.top()) + 8
        icon_rect = QRect(int(r.center().x() - s.width() / 2), top, s.width(), s.height())
        if isinstance(icon, QIcon):
            icon.paint(p, icon_rect)        # Normal mode: no selection tint on the page

        info = index.data(ROLE_INFO)
        if info:
            pos, name, page_no, color = info
            fm_font = QFont(option.font)
            fm_font.setBold(True)
            p.setFont(fm_font)
            p.setPen(QColor(C_ACCENT) if selected else QColor(C_TEXT))
            line_h = p.fontMetrics().height()
            y = icon_rect.bottom() + 6
            p.drawText(QRectF(r.left(), y, r.width(), line_h), Qt.AlignHCenter, f"Sayfa {pos}")

            small = QFont(option.font)
            small.setPointSizeF(max(7.0, option.font.pointSizeF() - 0.8))
            p.setFont(small)
            fm = p.fontMetrics()
            dot = 8
            avail = int(r.width()) - 16 - dot - 5
            text = fm.elidedText(f"{name} · s.{page_no}", Qt.ElideMiddle, avail)
            tw = fm.horizontalAdvance(text)
            total = dot + 5 + tw
            x0 = r.center().x() - total / 2
            y2 = y + line_h + 1
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(x0, y2 + (fm.height() - dot) / 2, dot, dot))
            p.setPen(QColor(C_MUTED))
            p.drawText(QRectF(x0 + dot + 5, y2, tw + 2, fm.height()), Qt.AlignLeft, text)
        p.restore()


class PageGrid(QListWidget):
    """Shows page thumbnails in a grid.

    Qt's built-in drag & drop in IconMode moves items to free positions instead
    of reordering them, so dragging/dropping is implemented here: the drop
    position is turned into an *insert index* and sent to the main window.
    """

    pagesDropped = Signal(int)              # move selected pages to this index
    filesDropped = Signal(list, int)        # files dropped from outside, index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pageGrid")
        self.setViewMode(QListView.IconMode)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setSpacing(4)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionRectVisible(True)
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WA_Hover)
        # setMovement(Static) disables dragging; turn it back on manually.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(False)
        self.setAutoScroll(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setItemDelegate(PageDelegate(self))

        self.empty_logo: QPixmap | None = None
        self._indicator: QRect | None = None
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(30)
        self._scroll_timer.timeout.connect(self._auto_scroll)

    # ---- starting a drag ------------------------------------------------- #
    def startDrag(self, supported_actions):
        items = self.selectedItems()
        if not items:
            return
        mime = QMimeData()
        mime.setData(PAGE_MIME, QByteArray(b"pages"))
        drag = QDrag(self)
        drag.setMimeData(mime)

        base = items[0].icon().pixmap(QSize(96, 96))
        if not base.isNull():
            pm = QPixmap(base.size())
            pm.setDevicePixelRatio(base.devicePixelRatio())
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setOpacity(0.9)
            p.drawPixmap(0, 0, base)
            p.setOpacity(1.0)
            if len(items) > 1:
                # badge with the number of dragged pages
                p.setRenderHint(QPainter.Antialiasing)
                r = QRect(int(pm.width() / pm.devicePixelRatio()) - 34, 2, 32, 22)
                p.setBrush(QColor(C_ACCENT))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(r, 11, 11)
                p.setPen(Qt.white)
                f = p.font()
                f.setBold(True)
                p.setFont(f)
                p.drawText(r, Qt.AlignCenter, str(len(items)))
            p.end()
            drag.setPixmap(pm)
            lw = int(pm.width() / pm.devicePixelRatio())
            lh = int(pm.height() / pm.devicePixelRatio())
            drag.setHotSpot(QPoint(lw // 2, lh // 2))
        drag.exec(Qt.MoveAction)

    # ---- drop position ---------------------------------------------------- #
    def _rect(self, row: int) -> QRect:
        return self.visualRect(self.model().index(row, 0))

    def drop_index(self, pos: QPoint) -> tuple[int, QRect | None]:
        """Turns a mouse position into an insert index and an indicator line."""
        n = self.count()
        if n == 0:
            return 0, None
        gap = max(2, self.spacing())
        found = None
        for r in range(n):
            rect = self._rect(r)
            if rect.top() - gap <= pos.y() <= rect.bottom() + gap:
                if pos.x() < rect.center().x():
                    return r, QRect(rect.left() - gap // 2 - 2, rect.top() + 6, 4, rect.height() - 12)
                found = (r + 1, QRect(rect.right() + gap // 2 - 1, rect.top() + 6, 4, rect.height() - 12))
        if found:
            return found
        if pos.y() < self._rect(0).top():
            rect = self._rect(0)
            return 0, QRect(rect.left() - gap // 2 - 2, rect.top() + 6, 4, rect.height() - 12)
        rect = self._rect(n - 1)
        return n, QRect(rect.right() + gap // 2 - 1, rect.top() + 6, 4, rect.height() - 12)

    @staticmethod
    def supported_paths(mime: QMimeData) -> list[str]:
        if not mime.hasUrls():
            return []
        out = []
        for url in mime.urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if path.lower().endswith(SUPPORTED_EXTS) and os.path.isfile(path):
                    out.append(path)
        return out

    def _accepts(self, event) -> bool:
        mime = event.mimeData()
        if mime.hasFormat(PAGE_MIME) and event.source() is self:
            return True
        return bool(self.supported_paths(mime))

    # ---- drag events ------------------------------------------------------ #
    def dragEnterEvent(self, event):
        if self._accepts(event):
            event.setDropAction(Qt.MoveAction if event.source() is self else Qt.CopyAction)
            event.accept()
            self._scroll_timer.start()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self._accepts(event):
            event.ignore()
            return
        _, self._indicator = self.drop_index(event.position().toPoint())
        self.viewport().update()
        event.setDropAction(Qt.MoveAction if event.source() is self else Qt.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._end_drag()
        event.accept()

    def dropEvent(self, event):
        idx, _ = self.drop_index(event.position().toPoint())
        self._end_drag()
        mime = event.mimeData()
        if mime.hasFormat(PAGE_MIME) and event.source() is self:
            # Report CopyAction so Qt does not try to remove the source items itself.
            event.setDropAction(Qt.CopyAction)
            event.accept()
            self.pagesDropped.emit(idx)
            return
        paths = self.supported_paths(mime)
        if paths:
            event.setDropAction(Qt.CopyAction)
            event.accept()
            # Loading may open dialogs; let the drag loop finish first.
            QTimer.singleShot(0, lambda: self.filesDropped.emit(paths, idx))
            return
        event.ignore()

    def _end_drag(self):
        self._scroll_timer.stop()
        self._indicator = None
        self.viewport().update()

    def _auto_scroll(self):
        pos = self.viewport().mapFromGlobal(QCursor.pos())
        h = self.viewport().height()
        margin = 40
        bar = self.verticalScrollBar()
        if pos.y() < margin:
            bar.setValue(bar.value() - max(4, (margin - pos.y()) // 2))
        elif pos.y() > h - margin:
            bar.setValue(bar.value() + max(4, (pos.y() - (h - margin)) // 2))

    # ---- painting --------------------------------------------------------- #
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.count() == 0:
            self._paint_empty_state(p)
        if self._indicator is not None:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C_ACCENT))
            p.drawRoundedRect(self._indicator, 2, 2)
        p.end()

    def _paint_empty_state(self, p: QPainter):
        area = self.viewport().rect()
        text_h = 60
        y = area.center().y() - 40
        if self.empty_logo is not None and not self.empty_logo.isNull():
            w = min(380, int(area.width() * 0.6))
            ratio = self.empty_logo.height() / self.empty_logo.width()
            h = int(w * ratio)
            y = area.center().y() - (h + text_h + 24) // 2
            p.setOpacity(0.13)
            p.drawPixmap(QRect(area.center().x() - w // 2, y, w, h), self.empty_logo)
            p.setOpacity(1.0)
            y += h + 24
        f = p.font()
        f.setPointSizeF(f.pointSizeF() * 1.2)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#475569"))
        p.drawText(QRect(area.left(), y, area.width(), 28), Qt.AlignHCenter,
                   "PDF veya görselleri buraya sürükleyip bırakın")
        f.setBold(False)
        f.setPointSizeF(f.pointSizeF() / 1.2)
        p.setFont(f)
        p.setPen(QColor(C_MUTED))
        p.drawText(QRect(area.left(), y + 30, area.width(), 24), Qt.AlignHCenter,
                   "ya da üstteki “Dosya Ekle” düğmesini kullanın  ·  PDF, PNG, JPG, TIFF, WebP…")


# --------------------------------------------------------------------------- #
#  File list (side panel)
# --------------------------------------------------------------------------- #
class FileList(QListWidget):
    """Loaded files. Can be reordered by dragging; emits a signal afterwards."""

    orderChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fileList")
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setIconSize(QSize(12, 12))
        self.setMouseTracking(True)

    def dropEvent(self, event):
        if event.source() is self:
            super().dropEvent(event)
            QTimer.singleShot(0, self.orderChanged.emit)
        else:
            event.ignore()   # external files are handled by the main window

    def dragEnterEvent(self, event):
        if event.source() is self:
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def doc_ids(self) -> list[int]:
        return [self.item(i).data(ROLE_DOC) for i in range(self.count())]


# --------------------------------------------------------------------------- #
#  Large preview dialog
# --------------------------------------------------------------------------- #
class PreviewDialog(QDialog):
    def __init__(self, main: "MainWindow", pos: int):
        super().__init__(main)
        self.main = main
        self.pos = pos
        self.setWindowTitle(f"Önizleme — {APP_NAME}")
        self.resize(760, 940)

        self.image = QLabel(alignment=Qt.AlignCenter)
        self.image.setObjectName("previewArea")
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image.setMinimumSize(200, 200)
        self.info = QLabel(alignment=Qt.AlignCenter)

        dark = "#334155"
        self.prev_btn = QPushButton(line_icon("left", dark, "#a0aec0", 18), " Önceki")
        self.next_btn = QPushButton(line_icon("right", dark, "#a0aec0", 18), " Sonraki")
        self.next_btn.setLayoutDirection(Qt.RightToLeft)
        close_btn = QPushButton("Kapat")
        self.prev_btn.clicked.connect(lambda: self.go(-1))
        self.next_btn.clicked.connect(lambda: self.go(1))
        close_btn.clicked.connect(self.accept)

        nav = QHBoxLayout()
        nav.addWidget(self.prev_btn)
        nav.addStretch(1)
        nav.addWidget(self.info)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)
        nav.addSpacing(12)
        nav.addWidget(close_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(self.image, 1)
        lay.addLayout(nav)
        QTimer.singleShot(0, self.render)

    def go(self, step: int):
        n = len(self.main.pages)
        if n == 0:
            return
        self.pos = max(0, min(n - 1, self.pos + step))
        self.render()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Left, Qt.Key_PageUp, Qt.Key_Up):
            self.go(-1)
        elif e.key() in (Qt.Key_Right, Qt.Key_PageDown, Qt.Key_Down, Qt.Key_Space):
            self.go(1)
        else:
            super().keyPressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.render()

    def render(self):
        pages = self.main.pages
        if not pages:
            self.image.clear()
            self.info.setText("—")
            return
        self.pos = max(0, min(len(pages) - 1, self.pos))
        ref = pages[self.pos]
        doc = self.main.docs[ref.doc_id]
        box = self.image.size()
        dpr = self.devicePixelRatioF()
        pm = render_page(doc.qdoc, ref.index, box.width() - 24, box.height() - 24, dpr)
        self.image.setPixmap(pm)
        self.info.setText(
            f"<b>{self.pos + 1} / {len(pages)}</b> &nbsp;&nbsp;"
            f"<span style='color:{C_MUTED}'>{doc.name} — sayfa {ref.index + 1}</span>"
        )
        self.prev_btn.setEnabled(self.pos > 0)
        self.next_btn.setEnabled(self.pos < len(pages) - 1)


# --------------------------------------------------------------------------- #
#  Main window
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1360, 840)
        self.setMinimumSize(760, 480)
        self.setAcceptDrops(True)

        self.docs: dict[int, SourceDoc] = {}    # all loaded files (kept for undo)
        self.doc_order: list[int] = []          # order shown in the side panel
        self.pages: list[PageRef] = []          # page order of the output PDF
        self._next_id = 1
        self.undo_stack: list[tuple] = []
        self.redo_stack: list[tuple] = []
        self.dirty = False
        self.last_dir = os.path.expanduser("~")

        self.thumb_size = 160
        self.thumbs: dict[PageRef, tuple[int, QIcon]] = {}
        self.render_queue: deque[PageRef] = deque()
        self.queued: set[PageRef] = set()
        self.item_by_ref: dict[PageRef, QListWidgetItem] = {}
        self.render_timer = QTimer(self)
        self.render_timer.setInterval(0)
        self.render_timer.timeout.connect(self._render_tick)

        self._build_ui()
        self._update_actions()

    # ---- UI --------------------------------------------------------------- #
    def _build_ui(self):
        light, dim = "#e2e8f0", "#55657c"

        def act(text, slot, icon, shortcut=None, tip=None):
            a = QAction(line_icon(icon, light, dim), text, self)
            if shortcut:
                if isinstance(shortcut, (list, tuple)):
                    a.setShortcuts([QKeySequence(s) for s in shortcut])
                else:
                    a.setShortcut(QKeySequence(shortcut))
            a.setToolTip(tip or text)
            a.triggered.connect(slot)
            self.addAction(a)
            return a

        self.a_open = act("Dosya Ekle", self.open_files, "add", QKeySequence.Open,
                          "PDF veya görsel ekle (Ctrl+O)")
        self.a_undo = act("Geri Al", self.undo, "undo", QKeySequence.Undo, "Geri al (Ctrl+Z)")
        self.a_redo = act("Yinele", self.redo, "redo", ["Ctrl+Y", "Ctrl+Shift+Z"],
                          "Yinele (Ctrl+Y)")
        self.a_delete = act("Sil", self.delete_selected, "trash", QKeySequence.Delete,
                            "Seçili sayfaları sil (Delete)")
        self.a_first = act("Başa", self.move_to_start, "first", "Ctrl+Home",
                           "Seçili sayfaları en başa taşı (Ctrl+Home)")
        self.a_left = act("Sola", lambda: self.shift_selected(-1), "left", "Ctrl+Left",
                          "Seçili sayfaları bir sola taşı (Ctrl+←)")
        self.a_right = act("Sağa", lambda: self.shift_selected(1), "right", "Ctrl+Right",
                           "Seçili sayfaları bir sağa taşı (Ctrl+→)")
        self.a_last = act("Sona", self.move_to_end, "last", "Ctrl+End",
                          "Seçili sayfaları en sona taşı (Ctrl+End)")
        self.a_reverse = act("Ters Çevir", self.reverse_pages, "reverse", None,
                             "Seçili sayfaların (seçim yoksa tümünün) sırasını ters çevir")
        self.a_select_all = act("Tümünü Seç", lambda: self.grid.selectAll(), "select", None,
                                "Tüm sayfaları seç (Ctrl+A)")
        self.a_clear = act("Temizle", self.clear_all, "clear", None,
                           "Tüm dosya ve sayfaları kaldır")
        self.a_save = QAction(line_icon("save", "#ffffff", "#7b8aa0", 20), "Kaydet", self)
        self.a_save.setShortcut(QKeySequence.Save)
        self.a_save.setToolTip("Sonucu PDF olarak kaydet (Ctrl+S)")
        self.a_save.triggered.connect(self.save_pdf)
        self.addAction(self.a_save)

        # Header bar: logo | actions (overflow into a "more" menu) | size | save
        header = QFrame()
        header.setObjectName("header")
        header.setMinimumHeight(84)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 18, 12)
        hl.setSpacing(0)

        logo = QLabel()
        logo_pm = QPixmap(asset_path("logo-white.png"))
        if not logo_pm.isNull():
            h = 52
            dpr = max(self.devicePixelRatioF() or 1.0, 2.0)
            scaled = logo_pm.scaledToHeight(int(h * dpr), Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(dpr)
            logo.setPixmap(scaled)
        else:
            logo.setText(f"<b style='color:white;font-size:14pt'>{APP_NAME}</b>")
        logo.setToolTip(APP_NAME)
        hl.addWidget(logo)
        hl.addSpacing(18)
        line = QFrame()
        line.setObjectName("headerLine")
        line.setFixedSize(1, 44)
        hl.addWidget(line)
        hl.addSpacing(8)

        tb = QToolBar("Araçlar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setContextMenuPolicy(Qt.PreventContextMenu)
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb.setIconSize(QSize(24, 24))
        tb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addAction(self.a_open)
        tb.addSeparator()
        for a in (self.a_undo, self.a_redo):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.a_delete, self.a_first, self.a_left, self.a_right,
                  self.a_last, self.a_reverse):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.a_select_all)
        tb.addAction(self.a_clear)
        ext = tb.findChild(QToolButton, "qt_toolbar_ext_button")
        if ext is not None:     # visible "more" button on the dark background
            ext.setIcon(line_icon("more", "#e2e8f0", "#5b6b82"))
            ext.setToolTip("Diğer araçlar")
        hl.addWidget(tb, 1)

        size_box = QWidget()
        sl = QVBoxLayout(size_box)
        sl.setContentsMargins(10, 2, 14, 2)
        sl.setSpacing(6)
        size_lbl = QLabel("Boyut")
        size_lbl.setAlignment(Qt.AlignCenter)
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(90, 340)
        self.size_slider.setValue(self.thumb_size)
        self.size_slider.setFixedWidth(120)
        self.size_slider.setToolTip("Küçük resim boyutu")
        self._size_timer = QTimer(self, singleShot=True, interval=180)
        self._size_timer.timeout.connect(self._apply_thumb_size)
        self.size_slider.valueChanged.connect(lambda _: self._size_timer.start())
        sl.addWidget(size_lbl)
        sl.addWidget(self.size_slider)
        hl.addWidget(size_box)

        save_btn = QToolButton()
        save_btn.setObjectName("primary")
        save_btn.setDefaultAction(self.a_save)
        save_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        save_btn.setIconSize(QSize(20, 20))
        save_btn.setCursor(Qt.PointingHandCursor)
        hl.addWidget(save_btn)
        self.header = header
        self.actions_bar = tb

        # Side panel: files
        side = QFrame()
        side.setObjectName("side")
        ll = QVBoxLayout(side)
        ll.setContentsMargins(14, 14, 12, 12)
        ll.setSpacing(6)
        title = QLabel("Dosyalar")
        title.setObjectName("panelTitle")
        hint = QLabel("Sürükleyerek dosya sırasını değiştirin; "
                      "sayfalar bu sıraya göre gruplanır.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        self.file_list = FileList()
        self.file_list.orderChanged.connect(self._files_reordered)
        self.file_list.itemSelectionChanged.connect(self._update_actions)
        self.file_list.itemDoubleClicked.connect(self._select_pages_of_file)

        dark, dis = "#334155", "#b4bfcd"
        btns = QHBoxLayout()
        btns.setSpacing(6)
        add_btn = QPushButton(line_icon("plus", dark, dis, 16), " Ekle")
        add_btn.clicked.connect(self.open_files)
        self.remove_file_btn = QPushButton(line_icon("minus", dark, dis, 16), " Kaldır")
        self.remove_file_btn.setToolTip("Seçili dosyaları ve tüm sayfalarını kaldır")
        self.remove_file_btn.clicked.connect(self.remove_selected_files)
        self.up_btn = QPushButton(line_icon("up", dark, dis, 16), "")
        self.down_btn = QPushButton(line_icon("down", dark, dis, 16), "")
        self.up_btn.setToolTip("Dosyayı yukarı taşı")
        self.down_btn.setToolTip("Dosyayı aşağı taşı")
        for b in (self.up_btn, self.down_btn):
            b.setFixedWidth(38)
        self.up_btn.clicked.connect(lambda: self.move_file(-1))
        self.down_btn.clicked.connect(lambda: self.move_file(1))
        btns.addWidget(add_btn, 1)
        btns.addWidget(self.remove_file_btn, 1)
        btns.addWidget(self.up_btn)
        btns.addWidget(self.down_btn)

        ll.addWidget(title)
        ll.addWidget(hint)
        ll.addSpacing(4)
        ll.addWidget(self.file_list, 1)
        ll.addLayout(btns)

        # Page grid
        self.grid = PageGrid()
        self.grid.empty_logo = QPixmap(asset_path("logo-dark.png"))
        self.grid.pagesDropped.connect(self.move_selected_to)
        self.grid.filesDropped.connect(self.add_files)
        self.grid.itemSelectionChanged.connect(self._update_actions)
        self.grid.itemDoubleClicked.connect(self._preview_item)
        self.grid.setContextMenuPolicy(Qt.ActionsContextMenu)
        for a in (self.a_delete, self.a_first, self.a_left, self.a_right,
                  self.a_last, self.a_reverse):
            self.grid.addAction(a)
        self._apply_grid_metrics()

        splitter = QSplitter()
        splitter.setHandleWidth(1)
        splitter.addWidget(side)
        splitter.addWidget(self.grid)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, 1090])

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(header)
        cl.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.status = QLabel()
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(
            QLabel("Sürükle-bırak ile sırala  ·  Delete ile sil  ·  Çift tıkla önizle")
        )

    def _apply_grid_metrics(self):
        s = self.thumb_size
        fm = self.grid.fontMetrics()
        self.grid.setIconSize(QSize(s, s))
        self.grid.setGridSize(QSize(s + 34, s + fm.height() * 2 + 30))

    # ---- loading files ---------------------------------------------------- #
    def open_files(self):
        pats = " ".join(f"*{e} *{e.upper()}" for e in SUPPORTED_EXTS)
        imgs = " ".join(f"*{e} *{e.upper()}" for e in IMAGE_EXTS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "PDF veya görsel seçin", self.last_dir,
            f"Desteklenen dosyalar ({pats});;PDF dosyaları (*.pdf *.PDF);;"
            f"Görseller ({imgs});;Tüm dosyalar (*)",
        )
        if paths:
            self.add_files(paths)

    def add_files(self, paths: list[str], insert_at: int | None = None):
        new_docs: list[SourceDoc] = []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for path in paths:
                doc = self._load_doc(path)
                if doc is not None:
                    new_docs.append(doc)
        finally:
            QApplication.restoreOverrideCursor()
        if not new_docs:
            return

        self.push_undo()
        new_pages = [PageRef(d.id, i) for d in new_docs for i in range(d.page_count)]
        for d in new_docs:
            self.docs[d.id] = d
            self.doc_order.append(d.id)
        if insert_at is None or insert_at >= len(self.pages):
            self.pages.extend(new_pages)
        else:
            self.pages[insert_at:insert_at] = new_pages
        self.last_dir = os.path.dirname(new_docs[-1].path)
        self.dirty = bool(self.pages)
        self.refresh(select=new_pages)

    def _load_doc(self, path: str) -> SourceDoc | None:
        name = os.path.basename(path)
        kind = "image" if path.lower().endswith(IMAGE_EXTS) else "pdf"
        try:
            if kind == "image":
                data = image_to_pdf(path)
            else:
                with open(path, "rb") as fh:
                    data = fh.read()
            reader = PdfReader(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            what = "görsel" if kind == "image" else "dosya"
            self._error(f"“{name}” {what} olarak açılamadı:\n{exc}")
            return None

        password = None
        if reader.is_encrypted:
            try:
                ok = reader.decrypt("")
            except Exception:  # noqa: BLE001
                ok = 0
            if ok:
                password = ""
            else:
                for attempt in range(3):
                    QApplication.restoreOverrideCursor()
                    pw, accepted = QInputDialog.getText(
                        self, "Şifreli PDF",
                        f"“{name}” şifreli.\nŞifreyi girin:"
                        + ("\n(Hatalı şifre, tekrar deneyin)" if attempt else ""),
                        QLineEdit.Password,
                    )
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    if not accepted:
                        return None
                    try:
                        if reader.decrypt(pw):
                            password = pw
                            break
                    except Exception as exc:  # noqa: BLE001
                        self._error(f"“{name}” şifresi çözülemedi:\n{exc}")
                        return None
                else:
                    self._error(f"“{name}” için şifre doğrulanamadı.")
                    return None

        try:
            page_count = len(reader.pages)
        except Exception as exc:  # noqa: BLE001
            self._error(f"“{name}” okunamadı:\n{exc}")
            return None
        if page_count == 0:
            self._error(f"“{name}” hiç sayfa içermiyor.")
            return None

        # QtPdf also reads from memory, so the source file is never kept open.
        # This makes it safe to overwrite a source file when saving (also on Windows).
        buf = QBuffer()
        buf.setData(QByteArray(data))
        buf.open(QIODevice.ReadOnly)
        qdoc = QPdfDocument(self)
        if password:
            qdoc.setPassword(password)
        qdoc.load(buf)
        if qdoc.status() != QPdfDocument.Status.Ready:
            self._error(f"“{name}” görüntülenemedi (hata: {qdoc.error().name}).")
            qdoc.deleteLater()
            return None

        doc_id = self._next_id
        self._next_id += 1
        color = QColor(DOC_COLORS[(doc_id - 1) % len(DOC_COLORS)])
        return SourceDoc(doc_id, os.path.abspath(path), name, kind, color,
                         reader, qdoc, buf, page_count)

    # ---- refreshing the view ---------------------------------------------- #
    def refresh(self, select: list[PageRef] | None = None, keep_scroll: bool = True):
        """Rebuilds the UI from the data model (self.pages / self.doc_order)."""
        if select is None:
            select = [it.data(ROLE_REF) for it in self.grid.selectedItems()]
        sel = set(select)
        scroll = self.grid.verticalScrollBar().value()

        # File list
        selected_docs = {it.data(ROLE_DOC) for it in self.file_list.selectedItems()}
        used: dict[int, int] = {}
        for ref in self.pages:
            used[ref.doc_id] = used.get(ref.doc_id, 0) + 1
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for did in self.doc_order:
            d = self.docs[did]
            n_used = used.get(did, 0)
            count = (f"{d.page_count} sayfa" if n_used == d.page_count
                     else f"{n_used}/{d.page_count} sayfa")
            if d.kind == "image":
                count += " · görsel"
            it = QListWidgetItem(dot_icon(d.color), f"{d.name}\n{count}")
            it.setData(ROLE_DOC, did)
            it.setToolTip(f"{d.path}\n{count}\nÇift tıklayın: bu dosyanın sayfalarını seç")
            self.file_list.addItem(it)
            if did in selected_docs:
                it.setSelected(True)
        self.file_list.blockSignals(False)

        # Page grid
        s = self.thumb_size
        self.grid.setUpdatesEnabled(False)
        self.grid.blockSignals(True)
        self.grid.clear()
        self.item_by_ref.clear()
        first_sel_item = None
        for pos, ref in enumerate(self.pages):
            d = self.docs[ref.doc_id]
            cached = self.thumbs.get(ref)
            icon = cached[1] if cached else placeholder_icon(s)
            it = QListWidgetItem(icon, f"Sayfa {pos + 1}")
            it.setData(ROLE_REF, ref)
            it.setData(ROLE_INFO, (pos + 1, d.name, ref.index + 1, d.color.name()))
            it.setToolTip(f"Çıktıda {pos + 1}. sayfa\n{d.path}\nKaynak sayfa: {ref.index + 1}")
            self.grid.addItem(it)
            self.item_by_ref[ref] = it
            if ref in sel:
                it.setSelected(True)
                if first_sel_item is None:
                    first_sel_item = it
        self.grid.blockSignals(False)
        self.grid.setUpdatesEnabled(True)
        if first_sel_item is not None:
            self.grid.setCurrentItem(first_sel_item, QItemSelectionModel.NoUpdate)
        if keep_scroll:
            self.grid.verticalScrollBar().setValue(scroll)

        self._schedule_thumbnails()
        self._update_actions()

    def _update_actions(self):
        n_sel = len(self.grid.selectedItems())
        has_pages = bool(self.pages)
        self.a_save.setEnabled(has_pages)
        self.a_delete.setEnabled(n_sel > 0)
        for a in (self.a_left, self.a_right, self.a_first, self.a_last):
            a.setEnabled(n_sel > 0)
        self.a_reverse.setEnabled(len(self.pages) > 1)
        self.a_select_all.setEnabled(has_pages)
        self.a_clear.setEnabled(bool(self.doc_order))
        self.a_undo.setEnabled(bool(self.undo_stack))
        self.a_redo.setEnabled(bool(self.redo_stack))
        has_file_sel = bool(self.file_list.selectedItems())
        self.remove_file_btn.setEnabled(has_file_sel)
        self.up_btn.setEnabled(has_file_sel)
        self.down_btn.setEnabled(has_file_sel)

        parts = [f"{len(self.pages)} sayfa", f"{len(self.doc_order)} dosya"]
        if n_sel:
            parts.append(f"{n_sel} seçili")
        self.status.setText("  ·  ".join(parts))
        title = APP_NAME
        if self.pages:
            title = f"{'● ' if self.dirty else ''}{APP_NAME} — {len(self.pages)} sayfa"
        self.setWindowTitle(title)

    # ---- thumbnails (rendered in small batches to keep the UI responsive) -- #
    def _schedule_thumbnails(self):
        s = self.thumb_size
        for ref in self.pages:
            cached = self.thumbs.get(ref)
            if (cached is None or cached[0] != s) and ref not in self.queued:
                self.render_queue.append(ref)
                self.queued.add(ref)
        if self.render_queue and not self.render_timer.isActive():
            self.render_timer.start()

    def _render_tick(self):
        deadline = time.monotonic() + 0.03       # at most ~30 ms per tick
        s = self.thumb_size
        dpr = self.grid.devicePixelRatioF()
        while self.render_queue and time.monotonic() < deadline:
            ref = self.render_queue.popleft()
            self.queued.discard(ref)
            cached = self.thumbs.get(ref)
            if cached is not None and cached[0] == s:
                continue
            doc = self.docs.get(ref.doc_id)
            if doc is None:
                continue
            icon = make_thumbnail(doc.qdoc, ref.index, s, dpr)
            self.thumbs[ref] = (s, icon)
            item = self.item_by_ref.get(ref)
            if item is not None:
                item.setIcon(icon)
        if not self.render_queue:
            self.render_timer.stop()

    def _apply_thumb_size(self):
        self.thumb_size = self.size_slider.value()
        self._apply_grid_metrics()
        # Re-plan pending work for the new size; old thumbnails stay until replaced.
        self.render_queue.clear()
        self.queued.clear()
        self.refresh()

    # ---- undo / redo ------------------------------------------------------ #
    def _snapshot(self):
        return (tuple(self.pages), tuple(self.doc_order))

    def push_undo(self):
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > 300:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _restore(self, snap):
        pages, order = snap
        self.pages = list(pages)
        self.doc_order = list(order)
        self.dirty = True
        self.refresh(select=[])

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())

    # ---- page operations -------------------------------------------------- #
    def selected_rows(self) -> list[int]:
        return sorted(self.grid.row(it) for it in self.grid.selectedItems())

    def _apply(self, new_pages: list[PageRef], select: list[PageRef] | None = None,
               new_order: list[int] | None = None):
        if new_pages == self.pages and (new_order is None or new_order == self.doc_order):
            return
        self.push_undo()
        self.pages = new_pages
        if new_order is not None:
            self.doc_order = new_order
        self.dirty = True
        self.refresh(select=select)

    def move_selected_to(self, insert: int):
        rows = self.selected_rows()
        if not rows:
            return
        rowset = set(rows)
        moving = [self.pages[i] for i in rows]
        rest = [p for i, p in enumerate(self.pages) if i not in rowset]
        insert -= sum(1 for i in rows if i < insert)
        new = rest[:insert] + moving + rest[insert:]
        self._apply(new, select=moving)

    def shift_selected(self, step: int):
        rows = self.selected_rows()
        if not rows:
            return
        sel = set(rows)
        pages = list(self.pages)
        flags = [i in sel for i in range(len(pages))]
        rng = range(len(pages)) if step < 0 else range(len(pages) - 1, -1, -1)
        for i in rng:
            j = i + step
            if flags[i] and 0 <= j < len(pages) and not flags[j]:
                pages[i], pages[j] = pages[j], pages[i]
                flags[i], flags[j] = flags[j], flags[i]
        self._apply(pages, select=[self.pages[i] for i in rows])
        self._scroll_to_selection()

    def move_to_start(self):
        self.move_selected_to(0)
        self._scroll_to_selection()

    def move_to_end(self):
        self.move_selected_to(len(self.pages))
        self._scroll_to_selection()

    def reverse_pages(self):
        rows = self.selected_rows()
        if len(rows) < 2:
            rows = list(range(len(self.pages)))
            select = []
        else:
            select = [self.pages[i] for i in rows]
        pages = list(self.pages)
        rev = [pages[i] for i in reversed(rows)]
        for i, ref in zip(rows, rev):
            pages[i] = ref
        self._apply(pages, select=select)

    def delete_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        rowset = set(rows)
        new = [p for i, p in enumerate(self.pages) if i not in rowset]
        nxt = min(rows[0], len(new) - 1)
        self._apply(new, select=[new[nxt]] if new else [])
        self._scroll_to_selection()

    def _scroll_to_selection(self):
        items = self.grid.selectedItems()
        if items:
            self.grid.scrollToItem(items[0])

    def _preview_item(self, item: QListWidgetItem):
        PreviewDialog(self, self.grid.row(item)).exec()

    def _select_pages_of_file(self, item: QListWidgetItem):
        did = item.data(ROLE_DOC)
        self.grid.clearSelection()
        first = None
        for ref, it in self.item_by_ref.items():
            if ref.doc_id == did:
                it.setSelected(True)
                if first is None or self.grid.row(it) < self.grid.row(first):
                    first = it
        if first is not None:
            self.grid.scrollToItem(first)
            self.grid.setFocus()

    # ---- file operations -------------------------------------------------- #
    def _regroup(self, order: list[int]) -> list[PageRef]:
        """Groups pages by file order (the order inside each file is kept)."""
        buckets: dict[int, list[PageRef]] = {d: [] for d in order}
        for ref in self.pages:
            if ref.doc_id in buckets:
                buckets[ref.doc_id].append(ref)
        return [ref for d in order for ref in buckets[d]]

    def _files_reordered(self):
        order = self.file_list.doc_ids()
        if order == self.doc_order:
            return
        self._apply(self._regroup(order), select=[], new_order=order)

    def move_file(self, step: int):
        sel = {it.data(ROLE_DOC) for it in self.file_list.selectedItems()}
        if not sel:
            return
        order = list(self.doc_order)
        flags = [d in sel for d in order]
        rng = range(len(order)) if step < 0 else range(len(order) - 1, -1, -1)
        for i in rng:
            j = i + step
            if flags[i] and 0 <= j < len(order) and not flags[j]:
                order[i], order[j] = order[j], order[i]
                flags[i], flags[j] = flags[j], flags[i]
        self._apply(self._regroup(order), select=[], new_order=order)

    def remove_selected_files(self):
        sel = {it.data(ROLE_DOC) for it in self.file_list.selectedItems()}
        if not sel:
            return
        order = [d for d in self.doc_order if d not in sel]
        pages = [p for p in self.pages if p.doc_id not in sel]
        self._apply(pages, select=[], new_order=order)

    def clear_all(self):
        if not self.doc_order:
            return
        self._apply([], select=[], new_order=[])
        self.dirty = False
        self._update_actions()

    # ---- saving ----------------------------------------------------------- #
    @staticmethod
    def default_file_name() -> str:
        """Suggested output name, e.g. pdf_14-35-07_14-11-2026.pdf (time_date)."""
        return datetime.now().strftime("pdf_%H-%M-%S_%d-%m-%Y.pdf")

    def save_pdf(self):
        if not self.pages:
            QMessageBox.information(self, APP_NAME, "Kaydedilecek sayfa yok.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF olarak kaydet", os.path.join(self.last_dir, self.default_file_name()),
            "PDF dosyası (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        QApplication.setOverrideCursor(Qt.WaitCursor)
        tmp = None
        try:
            writer = PdfWriter()
            for ref in self.pages:
                writer.add_page(self.docs[ref.doc_id].reader.pages[ref.index])
            writer.add_metadata({"/Producer": APP_NAME, "/Creator": APP_NAME})
            folder = os.path.dirname(os.path.abspath(path)) or "."
            fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=folder)
            with os.fdopen(fd, "wb") as fh:
                writer.write(fh)
            os.replace(tmp, path)   # write to a temp file first: no half-written output
            tmp = None
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            self._error(f"Kaydedilemedi:\n{exc}")
            return
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        self.last_dir = os.path.dirname(path)
        self.dirty = False
        self._update_actions()
        self.statusBar().showMessage(f"Kaydedildi: {path}", 6000)

    # ---- dropping files anywhere on the window ----------------------------- #
    def dragEnterEvent(self, event):
        if PageGrid.supported_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = PageGrid.supported_paths(event.mimeData())
        if paths:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda: self.add_files(paths))

    def closeEvent(self, event):
        if self.dirty and self.pages:
            ans = QMessageBox.question(
                self, APP_NAME,
                "Kaydedilmemiş değişiklikler var. Yine de çıkılsın mı?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()

    def _error(self, msg: str):
        cursor_overridden = QApplication.overrideCursor() is not None
        if cursor_overridden:
            QApplication.restoreOverrideCursor()
        QMessageBox.warning(self, APP_NAME, msg)
        if cursor_overridden:
            QApplication.setOverrideCursor(Qt.WaitCursor)


def main():
    if sys.platform == "win32":
        # Own taskbar group/icon on Windows instead of the generic Python one.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Aeronist.PDFEditor")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    # Toolbar icons are drawn for the dark header; keep menus text-only.
    app.setAttribute(Qt.AA_DontShowIconsInMenus, True)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Aeronist")
    app.setDesktopFileName(APP_ID)
    icon_path = asset_path("app-icon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    apply_theme(app)

    win = MainWindow()
    win.show()
    # Files given on the command line: python aeronist_pdf_editor.py a.pdf b.png
    files = [a for a in sys.argv[1:]
             if a.lower().endswith(SUPPORTED_EXTS) and os.path.isfile(a)]
    if files:
        QTimer.singleShot(0, lambda: win.add_files(files))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
