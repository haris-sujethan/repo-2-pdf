# repo2pdf/pdf.py
# Clean, readable PDF renderer with *native* syntax highlighting:
# - Cover
# - Table of Contents AT THE START (reserved then backfilled; truncates with a note)
# - Text-only Overview (LLM + human friendly; strips README images)
# - One section per file with Unicode-safe monospaced text
# - Native Pygments token coloring (no HTML), line numbers, light code background
# - Safe soft-wrapping; no empty background bands; robust around page breaks
# - Small-file packing: multiple tiny files share a page when space allows
# - Header shows: path • language • lines (per-page context)
# - Appendix: transparent “Skipped & condensed” summary

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Tuple, Optional, List, Dict, Any

from fpdf import FPDF

# Pygments for lexing & token types
from pygments import lex
from pygments.lexers import get_lexer_for_filename, guess_lexer
from pygments.lexers.special import TextLexer
from pygments.token import Token

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PACKAGE_DIR = os.path.dirname(__file__)
FONTS_DIR = os.path.join(PACKAGE_DIR, "fonts")

DEJAVU_SANS = os.path.join(FONTS_DIR, "DejaVuSans.ttf")
DEJAVU_SANS_BOLD = os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")
DEJAVU_MONO = os.path.join(FONTS_DIR, "DejaVuSansMono.ttf")

# Minimal text normalizer so DejaVu can render everything
CHAR_MAP = {
    # arrows, misc
    "⚠️": "⚠", "➡️": "→", "➡": "→", "⬅️": "←", "⬅": "←",
    # smart punctuation -> ASCII
    "–": "-", "—": "-", "―": "-", "−": "-",
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‚": "'", "‹": "'", "›": "'",
    "\u00A0": " ",  # NBSP
}

def normalize_text_for_pdf(s: str) -> str:
    s = (s or "").replace("️", "")  # strip variation selector
    for k, v in CHAR_MAP.items():
        s = s.replace(k, v)
    return s


@dataclass
class PDFMeta:
    title: str
    subtitle: Optional[str] = None
    repo_url: Optional[str] = None
    generated_at: Optional[datetime] = None


class RepoPDF(FPDF):
    """FPDF renderer with a cover, ToC at start, text Overview, and per-file sections."""

    def __init__(self, meta: PDFMeta):
        super().__init__(orientation="P", unit="mm", format="A4")
        # Slightly larger bottom margin so footers never collide
        self.set_auto_page_break(auto=True, margin=16)
        self.meta = meta
        self._toc: List[Tuple[str, int, int]] = []   # (label, level, page)
        self._links: Dict[str, int] = {}
        self._toc_reserved_page: Optional[int] = None
        # Header state (per page)
        self._hdr_path: str = meta.title
        self._hdr_lang: str = ""
        self._hdr_lines: Optional[int] = None

        self._register_fonts()
        self._set_doc_info()

    # ---------------------------- Fonts & metadata ----------------------------
    def _register_fonts(self):
        for path in (DEJAVU_SANS, DEJAVU_SANS_BOLD, DEJAVU_MONO):
            if not (os.path.exists(path) and os.path.getsize(path) > 50_000):
                raise RuntimeError(
                    f"Missing/invalid font at {path}. Please vendor real DejaVu TTF binaries."
                )
        # Register Unicode-safe fonts (regular + bold only; no italics to prevent errors)
        self.add_font("DejaVu", style="",  fname=DEJAVU_SANS,      uni=True)
        self.add_font("DejaVu", style="B", fname=DEJAVU_SANS_BOLD, uni=True)
        self.add_font("DejaVuMono", style="", fname=DEJAVU_MONO,   uni=True)
        self.set_font("DejaVu", size=11)

    def _set_doc_info(self):
        self.set_title(self.meta.title)
        if self.meta.subtitle:
            self.set_subject(self.meta.subtitle)
        if self.meta.repo_url:
            self.set_author(self.meta.repo_url)
        self.set_creator("repo2pdf")

    # ---------------------------- Header / Footer -----------------------------
    def header(self):
        # Header line + context
        self.set_font("DejaVu", size=9)
        self.set_text_color(60)
        self.set_x(self.l_margin)

        # Trim path to available width
        right_part = ""
        if self._hdr_lang or self._hdr_lines is not None:
            parts = [p for p in [self._hdr_lang, f"{self._hdr_lines} lines" if self._hdr_lines else None] if p]
            right_part = " • ".join(parts)
        max_w = self.w - self.l_margin - self.r_margin
        left_txt = normalize_text_for_pdf(self._hdr_path)
        if right_part:
            # reserve space for right_part
            rp_w = self.get_string_width("  " + right_part)
            avail = max_w - rp_w
            # elide left if too long
            while self.get_string_width(left_txt) > avail and len(left_txt) > 4:
                left_txt = "…" + left_txt[1:]
            self.cell(avail, 6, left_txt, ln=0, align="L")
            # right-aligned meta
            self.set_xy(self.w - self.r_margin - rp_w, self.get_y())
            self.cell(rp_w, 6, right_part, ln=1, align="R")
        else:
            self.cell(0, 6, left_txt, ln=1, align="L")

        self.set_draw_color(220)
        self.set_line_width(0.2)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(2)
        self.set_text_color(0)

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", size=9)
        self.set_text_color(120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(0)

    # ------------------------------- Helpers ----------------------------------
    def _page_width_available(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def _safe_multicell(self, text: str, line_h: float):
        """Reset X to left margin and use explicit width to avoid FPDF width errors."""
        self.set_x(self.l_margin)
        self.multi_cell(self._page_width_available(), line_h, text)

    # ------------------------------- High level --------------------------------
    def add_cover(self):
        # Header state for this page
        self._hdr_path = normalize_text_for_pdf(self.meta.title)
        self._hdr_lang = ""
        self._hdr_lines = None

        self.add_page()
        self.set_font("DejaVu", "B", 22)
        self.ln(30)
        self._safe_multicell(normalize_text_for_pdf(self.meta.title), line_h=12)
        self.ln(4)
        self.set_font("DejaVu", size=12)
        sub = self.meta.subtitle or "Repository to PDF"
        self._safe_multicell(normalize_text_for_pdf(sub), line_h=8)
        self.ln(4)
        if self.meta.repo_url:
            url = normalize_text_for_pdf(self.meta.repo_url)
            self.set_text_color(60, 90, 200)
            self.set_x(self.l_margin)
            self.cell(self._page_width_available(), 8, url, align="C", ln=1, link=self.meta.repo_url)
            self.set_text_color(0)
        self.ln(6)
        when = (self.meta.generated_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M UTC")
        self.set_text_color(120)
        self.set_x(self.l_margin)
        self.cell(self._page_width_available(), 8, f"Generated {when}", align="C")
        self.set_text_color(0)

    def reserve_toc_page(self):
        """Reserve a page right after the cover for the ToC and remember its number."""
        # Header state for ToC page
        self._hdr_path = "Table of Contents"
        self._hdr_lang = ""
        self._hdr_lines = None

        self.add_page()
        self._toc_reserved_page = self.page_no()

    def render_toc_on_reserved_page(self):
        if not self._toc_reserved_page:
            return
        # Jump to the reserved page and render
        current_page = self.page_no()
        current_x, current_y = self.get_x(), self.get_y()

        self.page = self._toc_reserved_page
        self.set_xy(self.l_margin, self.t_margin)

        self.set_font("DejaVu", "B", 16)
        self._safe_multicell("Table of Contents", line_h=10)
        self.ln(2)

        # Guard: don't let ToC overflow this single page (truncate gracefully)
        bottom_limit = self.h - self.b_margin
        self.set_font("DejaVu", size=11)
        truncated = False
        for label, level, page in self._toc:
            if self.get_y() + 8 > bottom_limit:
                truncated = True
                break
            indent = "    " * level
            text = f"{indent}{normalize_text_for_pdf(label)}"
            link_id = self._links.get(label)
            y_before = self.get_y()
            self.set_x(self.l_margin)
            self.cell(self._page_width_available(), 7, text, ln=0, link=link_id)
            self.set_xy(self.l_margin, y_before)
            self.cell(self._page_width_available(), 7, str(page), align="R", ln=1)

        if truncated:
            self.ln(1)
            self.set_font("DejaVu", "B", 10)
            self._safe_multicell("… ToC truncated", line_h=6)

        # Return to where we were (append mode)
        self.page = current_page
        self.set_xy(current_x, current_y)

    def toc_add(self, label: str, level: int = 0):
        self._toc.append((label, level, self.page_no()))
        # Internal link target bookkeeping
        try:
            link_id = self.add_link()
            self._links[label] = link_id
            self.set_link(link_id, y=self.get_y(), page=self.page_no())
        except Exception:
            pass

    # ------------------------------- Sections ----------------------------------
    def add_overview_section(self, overview: Dict[str, object]):
        """Overview section summarizing repo for humans & LLMs (text only)."""
        # Header state for this page
        self._hdr_path = "Overview"
        self._hdr_lang = ""
        self._hdr_lines = None

        self.add_page()
        title = "Overview"
        self.set_font("DejaVu", "B", 16)
        self._safe_multicell(title, line_h=10)
        self.ln(1)
        self.toc_add(title, level=0)

        self.set_font("DejaVu", size=11)
        line_h = 6

        def p(text: str = ""):
            self._safe_multicell(normalize_text_for_pdf(text), line_h=line_h)

        def bullet(text: str):
            self._safe_multicell(f"• {normalize_text_for_pdf(text)}", line_h=line_h)

        title_text = overview.get("title") or ""
        subtitle_text = overview.get("subtitle") or ""
        desc = overview.get("description") or ""
        features: List[str] = overview.get("features") or []
        usage = overview.get("usage") or ""
        exts: List[Tuple[str, int]] = overview.get("ext_counts") or []
        total_files: int = overview.get("total_files") or 0
        deps: List[str] = overview.get("dependencies") or []

        if title_text:
            self.set_font("DejaVu", "B", 12)
            p(str(title_text))
            self.set_font("DejaVu", size=11)
        if subtitle_text:
            p(str(subtitle_text))
        if desc:
            p(str(desc))

        if features:
            self.ln(1)
            self.set_font("DejaVu", "B", 12)
            p("Key Features")
            self.set_font("DejaVu", size=11)
            for f in features[:8]:
                bullet(str(f))

        if usage:
            self.ln(1)
            self.set_font("DejaVu", "B", 12)
            p("Quick Usage")
            self.set_font("DejaVuMono", size=10)
            self._safe_multicell(str(usage), line_h=5.5)
            self.set_font("DejaVu", size=11)

        if exts:
            self.ln(1)
            self.set_font("DejaVu", "B", 12)
            p("Files & Languages")
            self.set_font("DejaVu", size=11)
            for ext, cnt in exts[:8]:
                bullet(f"{ext} — {cnt} file(s)")
            bullet(f"Total files: {total_files}")

        if deps:
            self.ln(1)
            self.set_font("DejaVu", "B", 12)
            p("Dependencies")
            self.set_font("DejaVu", size=11)
            for d in deps[:12]:
                bullet(d)

    # ---- Code rendering with native syntax highlighting, background, line numbers
    def _ensure_lexer(self, rel_path: str, content: str):
        try:
            return get_lexer_for_filename(rel_path, stripnl=False)
        except Exception:
            try:
                return guess_lexer(content)
            except Exception:
                return TextLexer()

    def _write_code_with_highlighting(
        self,
        rel_path: str,
        content: str,
        *,
        line_numbers: bool = True,
        font_size: int = 9,
    ):
        """
        Write code using token-by-token coloring. Avoids drawing an empty band:
        we only draw the background after we know we'll print text on the line.
        """
        content = content.replace("\t", "    ")  # Normalize tabs
        lexer = self._ensure_lexer(rel_path, content)

        self.set_font("DejaVuMono", size=font_size)
        # line height tuned for DejaVuMono (readable & compact)
        line_h = max(4.6, font_size * 0.45 + 4.0)

        # Layout geometry
        left_x = self.l_margin
        right_x = self.w - self.r_margin
        bottom_limit = self.h - self.b_margin
        lines_total = (content.count("\n") + 1) if content else 1
        gutter_w = (self.get_string_width(str(lines_total)) + 4) if line_numbers else 0.0
        code_x = left_x + gutter_w

        # State for current visual line
        cur_line_no = 1
        at_line_start = True              # start of a visual line (no text yet)
        drew_band_this_line = False       # background band drawn?
        wrote_line_number = False         # line number drawn?

        def start_new_visual_line(new_logical: bool = False):
            nonlocal at_line_start, drew_band_this_line, wrote_line_number, cur_line_no
            # Move down a line; auto page break is on
            self.ln(line_h)
            at_line_start = True
            drew_band_this_line = False
            wrote_line_number = False
            # If this is because we finished a logical line, increment number now
            if new_logical:
                cur_line_no += 1

        def ensure_band_and_gutter():
            """Draw background + gutter only once, right before first text on the visual line."""
            nonlocal drew_band_this_line, wrote_line_number
            if drew_band_this_line:
                return
            y = self.get_y()
            if y + line_h > bottom_limit:
                # page is about to break; after break we are at new page top
                pass
            # Draw band
            self.set_fill_color(248, 248, 248)
            self.rect(left_x, y, right_x - left_x, line_h, style="F")
            # Gutter
            if line_numbers and not wrote_line_number:
                self.set_text_color(150, 150, 150)
                self.set_xy(left_x, y)
                self.cell(gutter_w, line_h, str(cur_line_no).rjust(len(str(lines_total))), align="R")
                wrote_line_number = True
            # Move to code start
            self.set_xy(code_x, y)
            drew_band_this_line = True

        # Begin at current Y; do not pre-draw anything
        if at_line_start:
            # just position cursor at code area before first text
            self.set_x(code_x)

        # Render each logical line with wrapping
        for logical_line in (content.splitlines(True) or [""]):
            pieces = list(lex(logical_line, lexer))

            for tok_type, txt in pieces:
                # Split into printable and whitespace chunks to allow wrapping at spaces
                for chunk in re.split(r"(\s+)", txt):
                    if chunk == "":
                        continue
                    if chunk == "\n":
                        # finish logical line: advance to next visual line as a new logical line
                        start_new_visual_line(new_logical=True)
                        continue

                    # We are about to print something: ensure band & gutter once
                    ensure_band_and_gutter()
                    at_line_start = False

                    # Soft wrap if needed
                    piece = chunk
                    while piece:
                        available = right_x - self.get_x()
                        piece_w = self.get_string_width(piece)

                        if piece_w <= available:
                            r, g, b = _rgb_for(tok_type)
                            self.set_text_color(r, g, b)
                            self.cell(piece_w, line_h, piece, ln=0)
                            piece = ""
                        else:
                            # Need to break piece — largest prefix that fits
                            lo, hi = 0, len(piece)
                            while lo < hi:
                                mid = (lo + hi + 1) // 2
                                if self.get_string_width(piece[:mid]) <= available:
                                    lo = mid
                                else:
                                    hi = mid - 1
                            prefix = piece[:lo] if lo > 0 else ""
                            rest = piece[lo:] if lo < len(piece) else ""
                            if prefix:
                                r, g, b = _rgb_for(tok_type)
                                self.set_text_color(r, g, b)
                                self.cell(self.get_string_width(prefix), line_h, prefix, ln=0)
                            # move to next visual line (continuation, same logical line number)
                            start_new_visual_line(new_logical=False)
                            ensure_band_and_gutter()
                            piece = rest

            # If the logical line did not end with "\n", we need to move to next logical line
            if not logical_line.endswith("\n"):
                start_new_visual_line(new_logical=True)

        # Reset color
        self.set_text_color(0, 0, 0)

    def _detect_language_label(self, rel_path: str, content: str) -> str:
        # Try pygments lexer name
        try:
            lexer = get_lexer_for_filename(rel_path, stripnl=False)
            return getattr(lexer, "name", "Text")
        except Exception:
            try:
                lexer = guess_lexer(content)
                return getattr(lexer, "name", "Text")
            except Exception:
                # Fall back to extension
                ext = os.path.splitext(rel_path)[1].lower() or "(no ext)"
                return {"": "Text"}.get(ext, ext or "Text")

    def _estimate_block_height(self, line_count: int, font_size: int = 9) -> float:
        """Rough height estimate for small-file packing (title + meta + lines)."""
        title_h = 9.0
        meta_h = 5.5
        line_h = max(4.6, font_size * 0.45 + 4.0)
        return title_h + 1 + meta_h + 1 + line_count * line_h + 2

    def _set_header_context(self, path: str, lang: str, lines: int):
        self._hdr_path = path
        self._hdr_lang = lang
        self._hdr_lines = lines

    def add_file_section(self, rel_path: str, content: str, *, force_new_page: bool = True):
        """Render a file. If force_new_page=False we try to keep adding on the same page."""
        # Body (code with native highlighting)
        content = normalize_text_for_pdf(content)
        # Safety: soft-wrap pathological long lines before rendering
        if content and len(max(content.splitlines() or [""], key=len)) > 2000:
            content = "\n".join(_soft_wrap(line, width=200) for line in content.splitlines())

        lang = self._detect_language_label(rel_path, content)
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        line_count = max(1, line_count)

        # Page decision for small files
        est_h = self._estimate_block_height(min(line_count, 40))
        bottom_limit = self.h - self.b_margin
        need_new_page = force_new_page or (self.get_y() + est_h > bottom_limit)

        if need_new_page:
            # Update header state for this page
            self._set_header_context(rel_path, lang, line_count)
            self.add_page()
        else:
            # Update header context to reflect the first file on this page
            if self.page_no() == 0:
                self.add_page()
            if self._hdr_path == self.meta.title:
                self._set_header_context(rel_path, lang, line_count)

        # File title
        self.set_font("DejaVu", "B", 14)
        self._safe_multicell(normalize_text_for_pdf(rel_path), line_h=9)

        # File meta line: language + line count
        self.set_font("DejaVu", size=9)
        self.set_text_color(110)
        meta_line = f"{lang} • {line_count} line(s)"
        self._safe_multicell(meta_line, line_h=5.5)
        self.set_text_color(0)
        self.ln(1)

        # ToC + link
        self.toc_add(rel_path, level=0)

        # Code
        self._write_code_with_highlighting(rel_path, content, line_numbers=True, font_size=9)

    # ------------------------------- Appendix ----------------------------------
    def add_appendix(self, summary: Optional[Dict[str, Any]]):
        if not summary:
            return

        self._hdr_path = "Appendix"
        self._hdr_lang = ""
        self._hdr_lines = None

        self.add_page()
        self.set_font("DejaVu", "B", 16)
        self._safe_multicell("Appendix: Skipped & condensed", line_h=10)
        self.ln(2)
        self.set_font("DejaVu", size=11)

        def row(label: str, value: Any):
            self.set_font("DejaVu", "B", 11)
            self._safe_multicell(label, line_h=6)
            self.set_font("DejaVu", size=11)
            self._safe_multicell(str(value), line_h=6)
            self.ln(1)

        counts = summary.get("counts", {})
        notes = summary.get("notes", [])
        packed = summary.get("packed_small_files", 0)

        row("Skipped (gitignored)", counts.get("gitignored", 0))
        row("Skipped (excluded dirs)", counts.get("excluded_dir", 0))
        row("Skipped (manual excludes)", counts.get("manual_exclude", 0))
        row("Skipped (binary by extension)", counts.get("binary_ext", 0))
        row("Skipped (binary by magic/heuristic)", counts.get("binary_magic", 0))
        row("Skipped (too large)", counts.get("too_large", 0))
        row("Read/decoding errors", counts.get("read_errors", 0))
        row("Packed small files (co-located per page)", packed)

        if notes:
            self.ln(2)
            self.set_font("DejaVu", "B", 12)
            self._safe_multicell("Notes", line_h=7)
            self.set_font("DejaVu", size=11)
            for n in notes:
                self._safe_multicell(f"• {n}", line_h=6)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pdf(
    files: Iterable[Tuple[str, str]],
    output_path: str,
    meta: Optional[PDFMeta] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate a polished PDF from an iterable of (relative_path, content).

    Adds:
      - Cover
      - Table of Contents (at the start; one page, truncated if needed)
      - Text Overview section (LLM + human friendly)
      - File sections (syntax-highlighted, small-file packing)
      - Appendix with skip/condense summary
    """
    meta = meta or PDFMeta(title="Repository Export", generated_at=datetime.utcnow())
    files = list(files)  # iterate twice safely
    pdf = RepoPDF(meta)

    # 1) Cover
    pdf.add_cover()

    # 2) Reserve a page for the ToC (at the start). We fill it later.
    pdf.reserve_toc_page()

    # 3) Overview
    overview = _build_overview_data(files, meta)
    pdf.add_overview_section(overview)

    # 4) Sections with small-file packing
    SMALL_LINE_THRESHOLD = 30
    current_page_small_lines = 0
    for rel_path, content in files:
        # Safety for pathological lines (still soft wrap later)
        if content and len(max(content.splitlines() or [""], key=len)) > 4000:
            content = "\n".join(_soft_wrap(line, width=200) for line in content.splitlines())

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        line_count = max(1, line_count)

        if line_count <= SMALL_LINE_THRESHOLD:
            # Try to keep adding on same page until space runs out
            pdf.add_file_section(rel_path, content, force_new_page=False)
            current_page_small_lines += line_count
        else:
            # Large file: force a new page
            current_page_small_lines = 0
            pdf.add_file_section(rel_path, content, force_new_page=True)

    # 5) Go back and render ToC on the reserved page (truncate if too long)
    pdf.render_toc_on_reserved_page()

    # 6) Appendix
    pdf.add_appendix(summary)

    # 7) Save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    pdf.output(output_path)
    return output_path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _soft_wrap(line: str, width: int) -> str:
    if len(line) <= width:
        return line
    return "\n".join(line[i:i+width] for i in range(0, len(line), width))

def _strip_readme_images(text: str) -> str:
    # Remove markdown image syntax ![alt](url) and <img ...> HTML tags
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"<img\s+[^>]*>", "", text, flags=re.IGNORECASE)
    return text

def _build_overview_data(files: List[Tuple[str, str]], meta: PDFMeta) -> Dict[str, object]:
    """
    Build a compact, LLM-friendly + human-friendly overview using repo content:
    - Name, purpose (from README if present)
    - Headline features (from README bullets)
    - Usage (from README or CLI hints)
    - Language & file stats
    - Dependencies (requirements.txt, pyproject)
    """
    file_map: Dict[str, str] = {p.lower(): c for p, c in files}

    # README
    readme_name = next((p for p, _ in files if os.path.basename(p).lower() in {"readme.md", "readme"}), None)
    readme = file_map.get(readme_name.lower(), "") if readme_name else ""
    readme = _strip_readme_images(readme)

    title = meta.title or "Repository"
    subtitle = meta.subtitle or ""

    # Description: first paragraph of README (strip headings)
    desc = ""
    if readme:
        text = re.sub(r"^#{1,6}\s+.*$", "", readme, flags=re.MULTILINE).strip()
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
        if parts:
            desc = parts[0][:800]

    # Features: README bullet list (first 5–8)
    features: List[str] = []
    if readme:
        for line in readme.splitlines():
            if re.match(r"^\s*[-*]\s+", line):
                features.append(re.sub(r"^\s*[-*]\s+", "", line).strip())
            if len(features) >= 8:
                break

    # Usage: a code snippet containing 'repo2pdf'
    usage = ""
    if readme:
        m = re.search(r"```(?:bash|sh)?\s*([^`]*repo2pdf[^\n`]*\n(?:.*?\n)*)```", readme, flags=re.IGNORECASE)
        if m:
            usage = m.group(1).strip()
    if not usage:
        usage = "repo2pdf  # Follow interactive prompts"

    # Language & file stats
    from collections import Counter
    ext_counts = Counter()
    for p, _ in files:
        ext = os.path.splitext(p)[1].lower() or "(no ext)"
        ext_counts[ext] += 1
    top_exts = sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
    file_count = sum(ext_counts.values())

    # Dependencies
    deps: List[str] = []
    req = file_map.get("requirements.txt", "")
    if req:
        for line in req.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                deps.append(line)
    pyproject = file_map.get("pyproject.toml", "")
    if pyproject and not deps:
        for name in ("fpdf2", "GitPython", "inquirer", "pathspec", "pygments", "pytest"):
            if name in pyproject and name not in deps:
                deps.append(name)

    return {
        "title": title,
        "subtitle": subtitle,
        "description": desc,
        "features": features,
        "usage": usage,
        "ext_counts": top_exts,
        "total_files": file_count,
        "dependencies": deps,
    }

# --- token color theme -------------------------------------------------------

# Simple light theme for tokens (tweak as you like)
THEME = {
    Token.Comment:        (120, 120, 120),
    Token.Keyword:        (170,  55, 140),
    Token.Keyword.Namespace: (170,  55, 140),
    Token.Name.Function:  ( 30, 120, 180),
    Token.Name.Class:     ( 30, 120, 180),
    Token.Name.Decorator: (135, 110, 180),
    Token.String:         ( 25, 140,  65),
    Token.Number:         (190, 110,  30),
    Token.Operator:       ( 90,  90,  90),
    Token.Punctuation:    ( 90,  90,  90),
    Token.Name.Builtin:   ( 30, 120, 180),
    Token.Name.Variable:  (  0,   0,   0),
    Token.Text:           (  0,   0,   0),
}

def _rgb_for(tok_type):
    # Find first mapping that contains this token type, else default black
    for t, rgb in THEME.items():
        if tok_type in t:
            return rgb
    return (0, 0, 0)
