"""Build presentation/CoreLoop_Final.pptx: 8 slides (intro, 6 content, demo video). python-pptx.

Every number is either computed here from the running engine (shipment plan, the two case studies),
read from benchmark/*.json (charts and tables), or copied from audit/validation_results.md.
All data is synthetic; each content slide says so in its footnote.
Run from the repo root or from presentation/:  python presentation/build_deck.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lxml import etree  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION  # noqa: E402
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

from coreloop.catalog import PARTS, POLICIES  # noqa: E402
from coreloop.models import ship_by  # noqa: E402
from data.store import Store  # noqa: E402
from ledger import operations as ops  # noqa: E402
from shipping.freight_cost_model import CORE_WEIGHT_LB, FreightParams, shipment_cost  # noqa: E402

# ----------------------------------------------------------------------------- style
BG, GREEN, ORANGE, INK = "F7F3EA", "1F4D3A", "B4572A", "2B2B2B"
MUTED, RULE, PANEL, SAGE = "7A7467", "CFC8B8", "EFE9DB", "8FA997"
FONT, MONO = "Arial", "Courier New"
SW, SH = 13.333, 7.5
TOTAL = 8


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(SW), Inches(SH)
BLANK = prs.slide_layouts[6]


def new_slide():
    s = prs.slides.add_slide(BLANK)
    f = s.background.fill
    f.solid()
    f.fore_color.rgb = rgb(BG)
    return s


def tx(slide, x, y, w, h, paras, size=12, color=INK, bold=False, font=FONT, align=PP_ALIGN.LEFT,
       anchor=MSO_ANCHOR.TOP, space=4, name=None, line_spacing=None):
    """paras: str | list of paragraphs; a paragraph is str | list of (text, opts) runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    if isinstance(paras, str):
        paras = [paras]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        if line_spacing:
            p.line_spacing = line_spacing
        runs = [(para, {})] if isinstance(para, str) else para
        for t, o in runs:
            r = p.add_run()
            r.text = t
            r.font.name = o.get("font", font)
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.italic = o.get("italic", False)
            r.font.color.rgb = rgb(o.get("color", color))
    return tb


def rect(slide, x, y, w, h, fill=None, line=None, lw=0.75, name=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    st = s._element.find(qn("p:style"))
    if st is not None:
        s._element.remove(st)
    return s


def hline(slide, x1, y, x2, color=RULE, w=0.75):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y), Inches(x2), Inches(y))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(w)
    st = c._element.find(qn("p:style"))
    if st is not None:
        c._element.remove(st)
    return c


def arrow(slide, x1, y1, x2, y2, color=INK, w=1.25):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(w)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    st = c._element.find(qn("p:style"))
    if st is not None:
        c._element.remove(st)
    return c


def dot(slide, cx, cy, r=0.07, fill=GREEN):
    return rect(slide, cx - r, cy - r, 2 * r, 2 * r, fill=fill, shape=MSO_SHAPE.OVAL)


def header(slide, n, label, title):
    tx(slide, 0.6, 0.42, 9, 0.25, f"{n:02d}  /  {label.upper()}", size=10, color=ORANGE, bold=True, name="Section")
    tx(slide, 0.6, 0.72, 12.1, 0.8, title, size=24, color=GREEN, bold=True, name="Title")


def footer(slide, n, note=None):
    if note and note.startswith("Source"):
        tx(slide, 0.6, 6.72, 12.1, 0.3, note, size=9, color=MUTED, name="Footnote")
    tx(slide, 0.6, 7.1, 8, 0.2, "Team Rasmalai  ·  CoreLoop  ·  Tek-Qubit: Women of Impact 2026", size=9, color=MUTED, name="Footer")
    tx(slide, 11.7, 7.1, 1.03, 0.2, f"{n} / {TOTAL}", size=9, color=MUTED, align=PP_ALIGN.RIGHT, name="PageNo")


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def cell_border(cell, bottom=None, top=None):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag, spec in (("a:lnL", None), ("a:lnR", None), ("a:lnT", top), ("a:lnB", bottom)):
        for old in tcPr.findall(qn(tag)):
            tcPr.remove(old)
        ln = etree.SubElement(tcPr, qn(tag))
        if spec:
            ln.set("w", str(int(spec[1] * 12700)))
            sf = etree.SubElement(ln, qn("a:solidFill"))
            c = etree.SubElement(sf, qn("a:srgbClr"))
            c.set("val", spec[0])
        else:
            ln.set("w", "0")
            etree.SubElement(ln, qn("a:noFill"))
    # fill must come after borders in schema order: move any fill element to the end
    for tag in ("a:noFill", "a:solidFill"):
        for el in tcPr.findall(qn(tag)):
            tcPr.remove(el)
            tcPr.append(el)


def table(slide, x, y, colw, rows, size=10.5, header_color=GREEN, row_h=0.27, bold_first_col=False, align=None, name=None):
    nrows, ncols = len(rows), len(colw)
    gf = slide.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(sum(colw)), Inches(row_h * nrows))
    if name:
        gf.name = name
    tbl = gf.table
    tblPr = tbl._tbl.tblPr
    for a in ("firstRow", "bandRow"):
        tblPr.set(a, "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is not None:
        sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"       # "No Style, No Grid"
    for j, w in enumerate(colw):
        tbl.columns[j].width = Inches(w)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.margin_left = Inches(0.04)
            c.margin_right = Inches(0.06)
            c.margin_top = c.margin_bottom = Inches(0.02)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.background()
            tf = c.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            if align and align[j] == "r":
                p.alignment = PP_ALIGN.RIGHT
            r = p.add_run()
            r.text = str(val)
            r.font.name = FONT
            r.font.size = Pt(size)
            hdr = i == 0
            r.font.bold = hdr or (bold_first_col and j == 0)
            r.font.color.rgb = rgb(header_color if hdr else INK)
            cell_border(c, bottom=(GREEN, 1.0) if hdr else (RULE, 0.5))
    return gf


def style_chart(ch, title=None, legend=False, size=10):
    ch.font.name = FONT
    ch.font.size = Pt(size)
    ch.font.color.rgb = rgb(INK)
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(size)
    if title:
        ch.has_title = True
        ch.chart_title.text_frame.text = title
        r = ch.chart_title.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.name, r.font.color.rgb = Pt(11), True, FONT, rgb(INK)
        ch.chart_title.include_in_layout = False
    else:
        ch.has_title = False


def axes(ch, ytitle, xtitle=None, fmt='#,##0', ymax=None):
    va, ca = ch.value_axis, ch.category_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb("E3DDCF")
    va.major_gridlines.format.line.width = Pt(0.5)
    va.format.line.fill.background()
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = fmt, False
    va.tick_labels.font.size = Pt(9)
    va.tick_labels.font.color.rgb = rgb(MUTED)
    va.has_title = True
    va.axis_title.text_frame.text = ytitle
    r = va.axis_title.text_frame.paragraphs[0].runs[0]
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(9), False, rgb(MUTED), FONT
    if ymax:
        va.maximum_scale = ymax
    va.minimum_scale = 0
    ca.format.line.color.rgb = rgb(RULE)
    ca.tick_labels.font.size = Pt(9)
    ca.tick_labels.font.color.rgb = rgb(INK)
    ca.has_major_gridlines = False
    if xtitle:
        ca.has_title = True
        ca.axis_title.text_frame.text = xtitle
        r = ca.axis_title.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(9), False, rgb(MUTED), FONT


def color_series(plot, colors):
    for s, col in zip(plot.series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(col)


def labels(plot, fmt, pos=None, size=9, color=INK):
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = fmt, False
    dl.font.size, dl.font.name, dl.font.color.rgb = Pt(size), FONT, rgb(color)
    if pos:
        dl.position = pos


# ----------------------------------------------------------------------------- screenshot crops
from PIL import Image  # noqa: E402
_ov = Image.open(HERE / "screens" / "operations-overview.png")
_ov.crop((0, 70, 1440, 870)).save(HERE / "screens" / "s_overview_side.png")
_ov.crop((340, 90, 1440, 785)).save(HERE / "screens" / "s_overview_main.png")

# ----------------------------------------------------------------------------- real data
BENCH = json.load(open(ROOT / "benchmark" / "audit_frequency_results.json"))
SHIPJ = json.load(open(ROOT / "benchmark" / "shipping_results.json"))
POL = BENCH["policies"]
A_, B_, C_, D_ = (POL[k] for k in ("A: every 90 days", "B: every 30 days", "C: every 7 days", "D: event-driven continuous"))
N_ = POL["N: no auditing (reference)"]
m = lambda d, k: d[k]["mean"]  # noqa: E731
SENS = {r["scenario"]: r for r in BENCH["sensitivity"]}

store = Store(os.path.join(tempfile.mkdtemp(), "deck.sqlite"))
W130 = ops.build_world(11, 600, 130, [])
PLAN = ops.plan_shipments(W130, 1)
FP = FreightParams()
plan_rows = []
for (oem, day), ids in sorted(PLAN["schedule"].items(), key=lambda x: (x[0][1], x[0][0])):
    cores = [PLAN["cores_by_id"][i] for i in ids]
    cost, loads, lb = shipment_cost(oem, [CORE_WEIGHT_LB[c.part_no] for c in cores], FP)
    tight = min(ship_by(c, POLICIES[oem]) - 130 for c in cores)
    plan_rows.append((oem, day, len(ids), lb, tight, cost))
weekly_events = len({(c.oem, c.removed_day + 1 + (4 - (c.removed_day + 1) % 7) % 7) for c in PLAN["cores_by_id"].values()})
money = lambda v: f"{'-' if v < 0 else '+'}${abs(v):,.0f}"  # noqa: E731
CF1, CF5 = ops.counterfactual_wait(W130, 1, 1), ops.counterfactual_wait(W130, 5, 1)

# case A: a real missed credit (core 515) and when the classifier flagged it
CASE_A = 515
traceA, prev = [], None
for t in range(56, 134):
    a = ops.build_world(11, 600, t, []).assessments[CASE_A]
    if a.state != prev:
        traceA.append((t, a.state, a.evidence.get("overdue_days"), a.evidence.get("normal_slow_tail_days"), a.evidence.get("history_n")))
        prev = a.state
cA = W130.cores[CASE_A]
aA = W130.assessments[CASE_A]
flag_day = next(r[0] for r in traceA if r[1] == "action_required")
DRAFT_A = ops.draft_dispute(W130, CASE_A).split("\n")

# case B: a slow credit the classifier correctly did not flag (core 228)
CASE_B = 228
wB = ops.build_world(11, 600, 140, [])
cB = wB.cores[CASE_B]
polB = POLICIES[cB.oem]
dueB = cB.received_day + polB.posting_days
rowsB = []
for t in range(dueB + polB.grace_days + 1, cB.credit_day):
    a = ops.build_world(11, 600, t, []).assessments[CASE_B]
    rowsB.append((t, a.evidence["overdue_days"], a.evidence["normal_slow_tail_days"], a.evidence["history_n"], a.state))
entB = PARTS[cB.part_no].core_value
assert all(r[4] != "action_required" for r in rowsB), "case B must stay un-alerted"


def R(label, text):
    return [(label + " ", {"bold": True}), (text, {})]


# ============================================================================= 1  intro
s = new_slide()
tx(s, 0.6, 0.5, 9, 0.25, "TEK-QUBIT: WOMEN OF IMPACT 2026  /  IDEATION ROUND", size=10, color=ORANGE, bold=True)
tx(s, 0.6, 0.9, 6.4, 0.7, "CoreLoop", size=34, color=GREEN, bold=True, name="Title")
tx(s, 0.6, 1.7, 6.3, 0.8, "The job isn't finished when the old part comes out.", size=20, color=INK, bold=True, line_spacing=1.05)
tx(s, 0.6, 2.55, 6.2, 2.0, [
    "When a dealership replaces a part, the old component doesn't just become waste. In many cases it still has financial value: "
    "the OEM can refund a core deposit if the part is returned correctly and on time.",
    "But between removing the part, shipping it back and receiving the credit, there are several chances for that value to slip away.",
    "We built CoreLoop to help dealerships catch those problems before it's too late."], size=12, space=7)
hline(s, 0.6, 4.6, 6.8)
tx(s, 0.6, 4.72, 3, 0.25, "TEAM", size=10, color=ORANGE, bold=True)
tx(s, 0.6, 5.0, 6, 0.9, [[("Rasmalai", {"size": 22, "bold": True, "color": INK})],
                          [("Riya Rana  ·  Dhriti Singh", {"size": 14, "color": INK})]], space=5)
tx(s, 0.6, 5.95, 6.2, 0.6, "Theme: circular parts. We work on the return leg, where a used core has to get back to the OEM and be paid for.",
   size=11, color=MUTED)
pic = s.shapes.add_picture(str(HERE / "screens" / "s_overview_side.png"), Inches(7.35), Inches(0.95), width=Inches(5.4))
pic.line.color.rgb, pic.line.width = rgb(RULE), Pt(0.75)
ph = Emu(pic.height).inches
tx(s, 7.35, 0.95 + ph + 0.06, 5.4, 0.3, "Our running prototype, day 130 of the simulated dealership: 115 open cores, 18 need action.", size=10, color=MUTED)
tx(s, 7.35, 4.75, 5.4, 0.25, "WHAT WE'VE BUILT SO FAR", size=10, color=ORANGE, bold=True)
tx(s, 7.35, 5.05, 5.4, 1.6, [
    "A working application with seven screens",
    "A shipment planner that groups cores without missing their return windows",
    "A credit monitor that tells delayed credits from potentially missing ones",
    "A simulator to compare audit schedules, backed by 67 automated tests"], size=12, space=5)
tx(s, 0.6, 6.72, 12.1, 0.3, "All figures come from a simulated dealership with assumed OEM rules and costs.",
   size=9, color=MUTED)
tx(s, 11.7, 7.1, 1.03, 0.2, f"1 / {TOTAL}", size=9, color=MUTED, align=PP_ALIGN.RIGHT)
notes(s, "Open with the story, not the product: 'When a dealership replaces a part, the old component doesn't just become waste. In many cases it still has financial value, because the OEM can refund a core deposit "
         "when it is returned correctly and on time. But between removing the part, shipping it back and receiving the credit, there are several opportunities for that value to get lost. "
         "We built CoreLoop to help dealerships catch those problems before it's too late.' Introduce Rasmalai: Riya and Dhriti. The screenshot is our running prototype and all data is synthetic.")

# ============================================================================= 2  problem
s = new_slide()
header(s, 2, "The problem", "A core is a deposit with a deadline, and there are three ways to lose it")
tx(s, 0.6, 1.5, 12.1, 0.85, [
    "A core return has a timeline. The dealership removes the part, ships it back, waits for the OEM to process it and finally receives the credit. "
    "A delay at any stage can cost the dealership money.",
    "And if nobody checks the process until the next audit, it may already be too late."], size=11.5, space=5)
X0, X1, Y = 0.9, 12.4, 2.95
sc = (X1 - X0) / 100.0
hline(s, X0, Y, X1, color=INK, w=1.5)
marks = [(0, "Core removed", "day 0", "up"), (18, "Last ship day", "day 18", "down"), (21, "OEM must receive", "day 21", "up"),
         (35, "Credit due", "day 35", "down"), (38, "Grace ends", "day 38", "up"), (98, "Dispute deadline", "day 98", "down")]
for d, lab, dd, pos in marks:
    cx = X0 + d * sc
    dot(s, cx, Y, 0.07, GREEN)
    ty = Y - 0.62 if pos == "up" else Y + 0.14
    tx(s, cx - 0.7, ty, 1.4, 0.5, [[(lab, {"bold": True, "size": 10})], [(dd, {"size": 9, "color": MUTED})]], align=PP_ALIGN.CENTER, space=0)
for a_, b_, lab in [(0, 21, "1  The part is never shipped, or arrives after the window closes"), (21, 38, "2  The credit never arrives"),
                    (38, 98, "3  The credit is wrong or short: old part number, extra deductions")]:
    xa, xb = X0 + a_ * sc, X0 + b_ * sc
    rect(s, xa, Y + 0.85, xb - xa - 0.04, 0.05, fill=ORANGE)
    tx(s, xa, Y + 0.95, xb - xa - 0.1, 0.45, lab, size=10, color=ORANGE, bold=True)
tx(s, 0.6, 4.42, 12.1, 0.25, "Illustrative OEM rules: 21-day window, 3 transit days, credit due 14 days after receipt, 3 grace days, 60-day dispute window.",
   size=9, color=MUTED)

tx(s, 0.6, 4.75, 3.8, 0.25, "WHAT REAL OEM RULES LOOK LIKE", size=10, color=ORANGE, bold=True)
table(s, 0.6, 5.0, [1.35, 2.45], [
    ["Source", "Rule (public)"],
    ["GM parts", "Core received within 6 months of purchase"],
    ["Cummins supplier", "Full credit to day 45, 90% to day 90"],
    ["Honda", "Credit cut or refused if damaged"],
    ["Subaru bulletin", "Non-compliant returns can be debited"]], size=9, row_h=0.29, name="PublicRules")
tx(s, 4.75, 4.75, 3.9, 0.25, "WHAT EXISTS TODAY", size=10, color=ORANGE, bold=True)
tx(s, 4.75, 5.03, 3.85, 1.5, [
    "Dealer and shop systems such as Tekmetric, R.O. Writer and Auto/Mate already track cores and post credits.",
    "In what we read, a person closes each credit by hand when a memo arrives. We found no planning against the return window and no time-aware check on a late credit. Not found is not the same as absent."],
   size=10, space=5)
tx(s, 9.0, 4.75, 3.7, 0.25, "WHAT NO CHECKING COSTS US", size=10, color=ORANGE, bold=True)
tx(s, 9.0, 4.97, 3.7, 0.6, f"${m(N_, 'total_loss'):,.0f}", size=30, color=GREEN, bold=True)
tx(s, 9.0, 5.6, 3.7, 1.0, [f"lost per 600-core synthetic ledger when nobody checks: ${m(N_, 'loss_window'):,.0f} in expired windows and "
   f"${m(N_, 'loss_credit_unrecovered'):,.0f} in credit never recovered. Even a 90-day audit still loses ${m(A_, 'total_loss'):,.0f}."], size=10)
footer(s, 2, "Sources: GM Parts, a Cummins remanufacturer policy, Honda dealer parts pages and a Subaru dealer bulletin (public documents, paraphrased).")
notes(s, "A core return is a timeline: remove, ship, wait for the OEM, receive the credit. There are three ways to lose the money: never shipped or late; credit never arrives; credit wrong or short. "
         "The $31,553 is the loss when nobody checks at all, the starting point of our benchmark. A 90-day audit still loses $26,051; that is the same ledger, different policy. "
         "Existing tools track cores; what we did not find is deadline-aware planning or a time-aware check on late credits.")

# ============================================================================= 3  prototype
s = new_slide()
header(s, 3, "The prototype", "We tested what happens when a dealership waits one more day")
LW = 3.9
p1 = s.shapes.add_picture(str(HERE / "screens" / "s_overview_main.png"), Inches(0.6), Inches(1.5), width=Inches(LW))
p1.line.color.rgb, p1.line.width = rgb(RULE), Pt(0.75)
h1 = Emu(p1.height).inches
tx(s, 0.6, 1.5 + h1 + 0.05, LW, 0.2, "Operations overview: open deposits by OEM and state.", size=9, color=MUTED)
y2 = 1.5 + h1 + 0.4
p2 = s.shapes.add_picture(str(HERE / "screens" / "s_counterfactual.png"), Inches(0.6), Inches(y2), width=Inches(LW))
p2.line.color.rgb, p2.line.width = rgb(RULE), Pt(0.75)
h2 = Emu(p2.height).inches
tx(s, 0.6, y2 + h2 + 0.05, LW, 0.2, "Counterfactual and ship-now alerts; buttons write to SQLite.", size=9, color=MUTED)

tx(s, 5.2, 1.5, 7.5, 0.8, "We created a simulated dealership with 600 cores across three OEMs; by day 130, 434 had been removed. "
   "The planner found 42 cores still waiting to ship. Instead of shipping each one separately, CoreLoop grouped them into three shipments while respecting every return deadline.",
   size=11)
tx(s, 5.2, 2.35, 7.5, 0.25, "THE SHIPMENT PLAN CORELOOP PRODUCED (DAY 130, 1-DAY SAFETY BUFFER)", size=10, color=ORANGE, bold=True)
rows = [["OEM", "Ship on", "Cores", "Weight (lb)", "Days left (tightest)", "Freight (sim.)"]]
for oem, day, n, lb, tight, cost in plan_rows:
    rows.append([oem, f"day {day}", n, f"{lb:,.0f}", tight, f"${cost:,.2f}"])
rows.append(["Total", "", sum(r[2] for r in plan_rows), f"{sum(r[3] for r in plan_rows):,.0f}", "", f"${sum(r[5] for r in plan_rows):,.2f}"])
table(s, 5.2, 2.62, [1.0, 1.1, 0.9, 1.3, 1.9, 1.3], rows, size=10, row_h=0.27, align=["l", "l", "r", "r", "r", "r"], name="ShipmentPlan")
tx(s, 5.2, 4.22, 7.5, 0.5, [R("The same 42 cores, three ways:", f"ship each one alone = 42 shipments; a weekly Friday run = {weekly_events}; CoreLoop = {PLAN['events']}. "
   "Cores 76 and 189 have zero days left, so the plan ships today.")], size=10.5)
tx(s, 5.2, 4.8, 7.5, 0.25, "WHAT IF THE DEALERSHIP WAITS?", size=10, color=ORANGE, bold=True)
table(s, 5.2, 5.07, [1.9, 1.4, 1.7, 1.6, 0.9], [
    ["Wait", "Cores lost", "Deposits lost", "Freight change", ""],
    ["1 day", CF1["wait"]["cores_lost"], f"${CF1['wait']['value_lost']:,.0f}", money(CF1['delta']['freight']), ""],
    ["5 days", CF5["wait"]["cores_lost"], f"${CF5['wait']['value_lost']:,.0f}", money(CF5['delta']['freight']), ""]],
      size=10, row_h=0.27, align=["l", "r", "r", "r", "l"], name="Counterfactual")
tx(s, 5.2, 6.28, 7.5, 0.4, f"Waiting one day saves ${abs(CF1['delta']['freight']):,.0f} of freight but puts {CF1['wait']['cores_lost']} cores at risk, with ${CF1['wait']['value_lost']:,.0f} in deposits exposed. "
   "", size=10.5)
footer(s, 3, "Synthetic scenario (seed 11, three invented OEMs). Freight uses our own illustrative weight and distance model. The plan is computed live by coreloop/shipping.py, not typed in.")
notes(s, "We built a simulated dealership with 600 cores across three OEMs. At day 130 the planner found 42 cores waiting to ship and grouped them into three shipments instead of 42, while respecting every deadline. "
         "Then the memorable bit: waiting just one day saves $11 of freight and puts two cores, $672 of deposits, out of reach. The table is the optimiser's real output, not a mock-up.")

# ============================================================================= 4  two cases
s = new_slide()
header(s, 4, "How it decides", "Not every late credit is a missing credit. We taught CoreLoop to tell the difference")
Y0 = 1.75
tx(s, 0.6, Y0, 6.0, 0.25, "CASE 1  ·  A CREDIT THAT NEVER ARRIVED", size=10, color=ORANGE, bold=True)
tx(s, 0.6, Y0 + 0.28, 6.0, 0.95, f"In our simulated dealership, a part worth ${aA.amount:,.0f} in expected credit went back to {cA.oem}. The OEM received it on day {cA.received_day}, but the credit never appeared. "
   f"CoreLoop did not raise an alarm straight away. It waited until the delay was clearly unusual for {cA.oem}, then flagged the case and prepared a dispute for the team to review.", size=10.5)
ax0, ax1, ay = 0.8, 6.2, 3.5
d0, d1 = 36, 138
scA = (ax1 - ax0) / (d1 - d0)
hline(s, ax0, ay, ax1, color=INK, w=1.25)
due = aA.evidence["credit_due"]
evA = [(cA.removed_day, f"Removed\nday {cA.removed_day}", "up", GREEN), (cA.shipped_day, f"Shipped\nday {cA.shipped_day}", "down", GREEN),
       (due + 3, f"Credit due {due},\ngrace ends {due+3}", "up", GREEN), (flag_day, f"Flagged\nday {flag_day}", "down", ORANGE),
       (aA.evidence["dispute_deadline"], f"Dispute deadline\nday {aA.evidence['dispute_deadline']}", "up", GREEN)]
for d, lab, pos, col in evA:
    cx = ax0 + (d - d0) * scA
    dot(s, cx, ay, 0.07, col)
    ty = ay - 0.62 if pos == "up" else ay + 0.14
    tx(s, cx - 0.65, ty, 1.3, 0.5, lab.split("\n"), size=9, align=PP_ALIGN.CENTER, space=0, color=INK)
rect(s, ax0 + (due + 3 + 1 - d0) * scA, ay - 0.03, (flag_day - (due + 4)) * scA, 0.06, fill=SAGE)
tx(s, 0.6, 4.2, 6.0, 0.7, f"The detail: part {cA.part_no}, core {CASE_A}. On day {traceA[1][0]} only {traceA[1][4]} comparable {cA.oem} credits had settled, too few to know what normal looks like, so it kept waiting. "
   f"By day {flag_day} the credit was {traceA[2][2]} days overdue, while a slow {cA.oem} credit normally takes at most {traceA[2][3]} days (from {traceA[2][4]} earlier credits). "
   f"That left {aA.evidence['dispute_deadline'] - flag_day} days before the dispute deadline.", size=9.5, color=MUTED)
rect(s, 0.6, 4.98, 6.0, 0.9, fill=PANEL)
tx(s, 0.7, 5.02, 5.8, 0.75, [[(l, {"font": MONO, "size": 8})] for l in DRAFT_A if l.strip()][:6], space=0)
tx(s, 0.6, 5.93, 6.0, 0.2, "A person reviews and submits the draft; CoreLoop never files on its own.", size=9.5, color=GREEN, bold=True)

tx(s, 7.05, Y0, 5.7, 0.25, "CASE 2  ·  A CREDIT THAT WAS SIMPLY LATE", size=10, color=ORANGE, bold=True)
tx(s, 7.05, Y0 + 0.28, 5.7, 0.95, f"Another credit, ${cB.credit_amount:,.2f} from {cB.oem}, was overdue by the book too, and a simple 'overdue means missing' rule would have opened a dispute on day {rowsB[0][0]}. "
   f"But {cB.oem} has a history of taking a few extra days on similar returns, so CoreLoop kept watching instead of raising a false alarm. "
   f"The credit arrived on day {cB.credit_day}, and no unnecessary dispute was created.", size=10.5)
rowsT = [["Day", "Days late", "Usual longest delay", "CoreLoop's call"]]
for t, od, tail, hn, st in rowsB:
    rowsT.append([t, od, f"{tail} days", "keep watching"])
rowsT.append([cB.credit_day, "", "", f"credit arrived, ${cB.credit_amount:,.2f}"])
table(s, 7.05, 3.1, [0.6, 1.1, 1.75, 2.25], rowsT, size=9.5, row_h=0.25, align=["r", "r", "r", "l"], name="FalseAlarm")
tx(s, 7.05, 3.1 + 0.25 * len(rowsT) + 0.12, 5.7, 0.9, f"The detail: 'days late' counts from the end of the grace days. {cB.oem}'s usual longest delay of {rowsB[-1][2]} days comes from {rowsB[-1][3]} credits it had already settled. "
   f"The delay never passed that, so the case stayed quietly on the watch list and closed itself.", size=9.5, color=MUTED)
hline(s, 0.6, 6.15, 12.7)
tx(s, 0.6, 6.22, 12.1, 0.45, [R("How well does it work?", "On held-out synthetic data from a second generator, alerts from a plain 'overdue = missing' rule were right 20.1% of the time, our first version 49.7%, "
   "and the final classifier 84.6%, still catching 99.8% of real misses. The price of patience: real misses are flagged about 20 days later than the naive rule would, but still before the dispute deadline.")],
   size=9.5)
footer(s, 4, "Both cases come from the synthetic demo scenario (seed 11), replayed day by day by the app's own classifier. Which credit is truly missing or slow is known only to the simulator, never to the classifier.")
notes(s, "Not every late credit is a missing credit. Case 1: a $140 credit never arrived. CoreLoop waited until the delay was clearly unusual for that OEM, flagged it, and drafted a dispute for a person to review. "
         "Case 2: a credit was late, but that OEM routinely takes a few extra days, so CoreLoop kept watching and the credit arrived. No false alarm, no wasted dispute. "
         "Be upfront about the price: real misses are flagged about 20 days later than the naive rule, still before the deadline. Our first version had 49.7% precision and we fixed it, then re-scored on seeds it had never seen.")

# ============================================================================= 5  decision flow
s = new_slide()
header(s, 5, "How it works", "We automated the checks. We kept the final decisions with people")
tx(s, 0.6, 1.5, 4, 0.25, "THE DAILY DECISION FLOW", size=10, color=ORANGE, bold=True)
rect(s, 5.4, 1.54, 0.14, 0.14, fill=GREEN)
tx(s, 5.62, 1.5, 1.8, 0.22, "CoreLoop checks", size=9.5, color=INK)
rect(s, 7.2, 1.54, 0.14, 0.14, fill=ORANGE)
tx(s, 7.42, 1.5, 1.8, 0.22, "A person decides", size=9.5, color=INK)


def step(x, y, title, sub, human=False, w=1.85, h=1.0):
    f = ORANGE if human else GREEN
    rect(s, x, y, w, h, fill=f, line=f)
    tx(s, x + 0.1, y + 0.07, w - 0.2, h - 0.1, [[(title, {"bold": True, "size": 10.5, "color": "FFFFFF"})], [(sub, {"size": 9, "color": "F3EEE3"})]], space=2)


XS = [0.6, 2.9, 5.2, 7.5]
tx(s, 0.6, 1.9, 8.7, 0.25, "1  CORES NOT YET SHIPPED", size=10, color=INK, bold=True)
step(XS[0], 2.2, "How many days are left?", "Time to the OEM's deadline, minus a safety buffer")
step(XS[1], 2.2, "Group them by OEM", "Fewest boxes that still beat every deadline")
step(XS[2], 2.2, "Raise a ship-now alert", "For cores with no slack left")
step(XS[3], 2.2, "Ship, defer or dismiss", "The dealership makes the call", human=True)
for i in range(3):
    arrow(s, XS[i] + 1.85, 2.7, XS[i + 1], 2.7)
for x, t in zip(XS[:2], ["coreloop/shipping.py", "shipping/freight_cost_model.py"]):
    tx(s, x, 3.25, 2.2, 0.2, t, size=8, color=MUTED, font=MONO)
tx(s, 0.6, 3.75, 8.7, 0.25, "2  SHIPPED, CREDIT NOT YET POSTED", size=10, color=INK, bold=True)
step(XS[0], 4.05, "Is the credit overdue?", "Due date plus the OEM's grace days")
step(XS[1], 4.05, "Is that unusual for this OEM?", "Compare with how long it really takes")
step(XS[2], 4.05, "Draft and rank disputes", "Ordered by value per staff minute")
step(XS[3], 4.05, "Review and submit", "Read the draft, then file or drop it", human=True)
for i in range(3):
    arrow(s, XS[i] + 1.85, 4.55, XS[i + 1], 4.55)
tx(s, XS[0], 5.1, 4.4, 0.2, "audit/temporal_credit_classifier.py", size=8, color=MUTED, font=MONO)
tx(s, XS[2], 5.1, 4.0, 0.2, "coreloop/disputes.py (CP-SAT)", size=8, color=MUTED, font=MONO)
tx(s, 2.9, 5.38, 6.4, 0.25, "Normal for this OEM: keep watching.   Records that don't add up: data error.", size=9.5, color=INK)
tx(s, 0.6, 5.85, 8.7, 0.8, [R("Under the hood.", "ledger/operations.py joins these steps; data/store.py saves every decision to SQLite; ui/app.py only draws the screens. "
   "The planner and classifier see only what is visible on the day; hidden simulator draws never reach them. 67 automated tests cover this.")], size=9.5, color=MUTED)

tx(s, 9.75, 1.5, 3.0, 0.25, "WHAT WE KEPT FOR PEOPLE", size=10, color=ORANGE, bold=True)
tx(s, 9.75, 1.85, 3.0, 4.9, [
    R("Filing a dispute.", "CoreLoop drafts and ranks; a person decides, because a dispute costs staff time and an OEM relationship."),
    R("A $0 credit on a damaged core.", "Often a fair rejection, so it goes to review, not to dispute."),
    R("Records that don't add up.", "Received before shipped, unknown part, negative credit: flagged as data errors, never turned into claims."),
    R("Judging damage.", "The recorded condition is an input. We don't second-guess it."),
    [("Why we drew the line here. ", {"bold": True, "color": GREEN}), ("In our validation, nearly every false alert came from legitimate OEM rejections (221) and genuinely slow credits (80). "
      "Those are the cases where someone with the paperwork should decide.", {"color": GREEN})]], size=10, space=7)
footer(s, 5, "Boxes follow the real code path; file names are from the repository. Classifier validation counts are pooled over 30 held-out synthetic seeds (audit/validation_results.md).")
notes(s, "We automated the checks and kept the decisions with people. Top row: what to ship and when. Bottom row: what to do about a credit that has not arrived. Orange boxes are where a person decides. "
         "We deliberately did not automate filing disputes, $0 credits on damaged cores, or records that do not add up. In validation almost every false alert came from legitimate OEM rejections and slow credits, which is exactly where a human with the paperwork should decide.")

# ============================================================================= 6  results
s = new_slide()
header(s, 6, "What we found", "We found that checking more often helps, but continuous monitoring isn't always better")
ALL = (N_, A_, B_, C_, D_)
cd = CategoryChartData()
cd.categories = ["No checks", "Every 90 days", "Every 30 days", "Every 7 days", "Continuous"]
cd.add_series("Expired return windows", [round(m(x, "loss_window")) for x in ALL])
cd.add_series("Unrecovered credit shortfall", [round(m(x, "loss_credit_unrecovered")) for x in ALL])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(0.5), Inches(1.75), Inches(5.9), Inches(2.6), cd)
gf.name = "LossByPolicy"
ch = gf.chart
style_chart(ch, "Loss per 600-core ledger by audit policy", legend=True)
axes(ch, "Dollars lost per ledger", None, fmt='"$"#,##0')
color_series(ch.plots[0], [GREEN, ORANGE])
ch.plots[0].gap_width = 55
for si, ser in enumerate(ch.plots[0].series):
    dl = ser.data_labels
    dl.show_value = True
    dl.number_format, dl.number_format_is_linked = '"$"#,##0', False
    dl.font.size, dl.font.name, dl.font.color.rgb = Pt(8.5), FONT, rgb("FFFFFF")
    dl.position = XL_LABEL_POSITION.CENTER
for i, v in enumerate(ch.plots[0].series[0].values):
    if v < 1000:
        pdl = ch.plots[0].series[0].points[i].data_label
        pdl.has_text_frame = True
        pdl.text_frame.text = " "

cd2 = CategoryChartData()
cd2.categories = ["Windows x0.5", "Base case", "Windows x2", "Windows x4"]
keys = ["return windows x0.5 (tighter)", "base case", "return windows x2", "return windows x4 (like long retail policies)"]
for lab, k in (("30-day audit", "loss_B"), ("7-day audit", "loss_C"), ("Continuous", "loss_D")):
    cd2.add_series(lab, [round(SENS[kk][k]) for kk in keys])
gf2 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(6.6), Inches(1.75), Inches(6.2), Inches(2.6), cd2)
gf2.name = "LossByWindow"
ch2 = gf2.chart
style_chart(ch2, "Loss by return-window length (60 seeds each)", legend=True)
axes(ch2, "Dollars lost per ledger", None, fmt='"$"#,##0')
color_series(ch2.plots[0], [SAGE, MUTED, GREEN])
ch2.plots[0].gap_width = 70
labels(ch2.plots[0], '"$"0.0,"k"', XL_LABEL_POSITION.OUTSIDE_END, 8)

tx(s, 0.6, 4.45, 6, 0.25, "PER LEDGER, 200 PAIRED SEEDS", size=10, color=ORANGE, bold=True)
rows = [["Policy", "Total loss", "Staff hours", "Disputes won", "Cash recovered"]]
for lab, x in (("No checks", N_), ("Every 90 days", A_), ("Every 30 days", B_), ("Every 7 days", C_), ("Continuous", D_)):
    rows.append([lab, f"${m(x,'total_loss'):,.0f}", f"{m(x,'staff_minutes')/60:.1f}", f"{m(x,'approved'):.1f}", f"${m(x,'cash_received'):,.0f}"])
table(s, 0.6, 4.72, [1.5, 1.1, 1.1, 1.15, 1.3], rows, size=9.5, row_h=0.26, align=["l", "r", "r", "r", "r"], name="PolicyTable")
tx(s, 7.0, 4.45, 5.7, 0.25, "WHAT WE LEARNED", size=10, color=ORANGE, bold=True)
gapCD = m(D_, "total_loss") - m(C_, "total_loss")
tx(s, 7.0, 4.72, 5.7, 2.0, [
    f"We tested four audit schedules, and no checking at all, on 200 paired synthetic ledgers. Going from a 90-day audit to a weekly one cut simulated loss from ${m(A_, 'total_loss'):,.0f} to ${m(C_, 'total_loss'):,.0f} per ledger.",
    f"Continuous monitoring ended almost level with weekly auditing: ${m(D_, 'total_loss'):,.0f} against ${m(C_, 'total_loss'):,.0f}, about ${gapCD:,.0f} apart, in the weekly audit's favour. "
    f"Its real edge is staff time ({m(D_, 'staff_minutes')/60:.0f} hours against {m(C_, 'staff_minutes')/60:.0f}) and robustness: if only half the weekly audits actually happen, that loss rises to ${SENS['human audits only happen 50% of the time']['loss_C']:,.0f}.",
    "The best schedule also depends on how quickly OEM windows expire: with tight windows continuous monitoring leads; with long windows even a 30-day audit is enough."],
   size=9.5, space=4)
footer(s, 6, "Synthetic. Charts and table are read from benchmark/audit_frequency_results.json (expired-window loss is $92 at 7 days and $206 continuous, too thin to label). 'No checks' is the same ledgers with no auditing, the baseline on slide 2.")
notes(s, "We tested four audit schedules plus no checking across 200 paired synthetic scenarios. Weekly auditing cut simulated loss from $26k to $4.3k. Continuous monitoring performed almost identically: about $114 per ledger apart, "
         "in weekly's favour, so we do not claim it wins on dollars. What it does give is far less staff time and resilience when audits get skipped. And the best schedule depends on how fast OEM windows expire. "
         "Do not hide the weekly-versus-continuous result; it makes the work more credible. The 'No checks' bar is the $31,553 baseline from slide 2, so the numbers reconcile.")

# ============================================================================= 7  fit
s = new_slide()
header(s, 7, "Where it fits", "Where CoreLoop fits into the dealership workflow")
labs = ["Weekly Friday", "Deadline rule", "Optimised, buffer 0", "Optimised, buffer 1", "Optimised, buffer 2", "Optimised, buffer 3"]
pk = list(SHIPJ["policies"].keys())
cd3 = CategoryChartData()
cd3.categories = labs
cd3.add_series("Shipments per 300-core ledger", [round(SHIPJ["policies"][k]["shipment_events"], 1) for k in pk])
gf3 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.5), Inches(5.4), Inches(2.9), cd3)
gf3.name = "Shipments"
ch3 = gf3.chart
style_chart(ch3, "Shipments needed per 300-core ledger", legend=False)
axes(ch3, "Shipments per ledger", "Shipping policy", fmt='0')
ch3.plots[0].gap_width = 50
labels(ch3.plots[0], '0.0', XL_LABEL_POSITION.OUTSIDE_END, 9)
for i, pt in enumerate(ch3.plots[0].series[0].points):
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = rgb(MUTED if i < 2 else GREEN)
ch3.category_axis.tick_labels.font.size = Pt(8)
fr = [SHIPJ["policies"][k]["freight"] for k in pk]
tx(s, 0.6, 4.5, 5.3, 2.2, [
    R("Fewer shipments, same deadlines.", f"A weekly Friday run costs ${fr[0]:,.0f} in simulated freight per ledger; CoreLoop with a one-day safety buffer costs ${fr[3]:,.0f} ({100*(1-fr[3]/fr[0]):.0f}% less). "
      "After expected window losses the gain is small (-$859 to +$723 per ledger depending on the buffer), so we don't claim big freight savings."),
    R("Carrier delays matter.", "A 3-day buffer is best in our base, high and severe delay cases; 2 days when delay risk is low. The shipment screen has a 0 to 3 day buffer slider.")],
   size=10.5, space=6)

tx(s, 6.35, 1.5, 6.4, 0.25, "WHERE IT FITS", size=10, color=ORANGE, bold=True)
tx(s, 6.35, 1.78, 6.4, 1.2, [
    "We looked at Tekion's publicly available product information before defining our scope. Existing dealership systems already manage parts and credits, and we aren't trying to replace those workflows.",
    "Our focus is the decisions that connect them: when to ship a core, whether a return is at risk, and whether an expected credit needs attention."], size=10.5, space=5)
tx(s, 6.35, 3.05, 6.4, 0.25, "WHAT TEKION'S PUBLIC DOCUMENTATION SHOWS", size=10, color=ORANGE, bold=True)
table(s, 6.35, 3.32, [2.45, 1.25, 2.7], [
    ["Question", "Status", "What we found"],
    ["Partner platform for third-party apps?", "Confirmed", "390 APIs, 500+ partners listed"],
    ["Handles part-number changes?", "Partial", "Special-order parts only"],
    ["Parts connected to OEMs?", "Partial", "General statements"],
    ["Core deposits and credit-memo reconciliation?", "Not found", "No public page found"],
    ["Return-window alerts?", "Not found", "No public page found"]], size=9.5, row_h=0.28, name="TekionFit")
tx(s, 6.35, 5.1, 6.4, 0.3, "Not found means we could not see it, not that it does not exist.", size=10.5, color=GREEN, bold=True)
tx(s, 6.35, 5.42, 3.0, 0.25, "LIMITS WE STATE", size=10, color=ORANGE, bold=True)
tx(s, 6.35, 5.68, 3.1, 1.0, [
    "All data synthetic; rules and rates are assumptions",
    "On dollars, continuous only ties weekly auditing",
    "About 1 credit alert in 7 is still wrong"], size=9, space=2)
tx(s, 9.7, 5.42, 3.05, 0.25, "IF WE REACH THE PROTOTYPE ROUND", size=10, color=ORANGE, bold=True)
tx(s, 9.7, 5.68, 3.05, 1.0, [
    [("1  ", {"bold": True}), ("Replace invented rules with real windows", {})],
    [("2  ", {"bold": True}), ("Backtest on one dealer's history", {})],
    [("3  ", {"bold": True}), ("Share a spare core between dealers' shipments", {})]], size=9, space=2)
footer(s, 7, "Source: Tekion's publicly available product information.")
notes(s, "Where CoreLoop fits: we read Tekion's public product information first. Existing systems already manage parts and credits, so we are not replacing them; we focus on the decisions that connect them: when to ship, is a return at risk, does a credit need attention. "
         "The table shows what we confirmed, what was partial and what we could not find. 'Not found' means we could not see it, not that it does not exist. Never claim Tekion lacks a feature. "
         "Shipping: say fewer shipments and lower simulated freight; the net gain is small and we say so.")

# ============================================================================= 8  video
s = new_slide()
header(s, 8, "Demo", "Watch CoreLoop work through one day in a simulated dealership")
vx, vy, vw = 0.6, 1.5, 5.0
vh = vw * 900 / 1400
mv = s.shapes.add_movie(str(HERE / "CoreLoop_demo.mp4"), Inches(vx), Inches(vy), Inches(vw), Inches(vh),
                        poster_frame_image=str(HERE / "screens" / "video_poster.png"), mime_type="video/mp4")
mv.name = "DemoVideo"
if not os.environ.get("PDF_MODE"):
    tx(s, vx, vy + vh + 0.08, vw, 0.3, "Video: click on play", size=10, color=MUTED)
tx(s, 0.6, 5.2, 5.4, 0.25, "WHERE WE LANDED", size=10, color=ORANGE, bold=True)
tx(s, 0.6, 5.45, 5.5, 1.25, [
    "We started with a simple question: what happens to the value of a part after it leaves the vehicle?",
    "CoreLoop helps dealerships protect that value by making core returns more timely and credit discrepancies easier to catch.",
    "We haven't solved every part of the circular-parts ecosystem, but we've built and tested the core decision engine for one important part of it."],
   size=9.5, space=3, color=GREEN)
tx(s, 6.35, 1.5, 6.4, 0.25, "WHAT IS HAPPENING, STEP BY STEP", size=10, color=ORANGE, bold=True)
chap = [("0:00", "Operations overview", "The simulated dealership on day 130: 115 cores still open, 18 need action today."),
        ("0:09", "Shipment optimisation", "The planner packs the 42 unshipped cores into 3 shipments that still meet every OEM deadline."),
        ("0:18", "Counterfactual", "Waiting one more day saves $11 of freight but puts 2 cores ($672 of deposits) out of reach."),
        ("0:25", "Ship core 76", "Core 76 has zero days left. We click Ship today; the decision is saved and its alert disappears."),
        ("0:36", "Credit monitoring", "Overdue credits, each judged against how long that OEM normally takes to post."),
        ("0:45", "Dispute queue", "Drafted disputes ranked by expected value per staff minute. A person reads the draft first."),
        ("1:00", "Submit, then advance", "Two disputes are submitted and the clock moves a week. Outcomes are simulated and labelled so."),
        ("1:10", "Audit-frequency simulator", "The benchmark compares audit schedules on identical ledgers."),
        ("1:23", "Audit trail", "Every decision made in the demo is logged with its reason and survives a restart.")]
table(s, 6.35, 1.78, [0.55, 1.7, 4.15], [["Time", "Scene", "What is happening"]] + [list(c) for c in chap], size=9, row_h=0.47, name="Chapters")
notes(s, "Play the video (about 1 min 34 s) or run the app live. Talk through it with the step table. Then close: 'We started with a simple question: what happens to the value of a part after it leaves the vehicle? "
         "CoreLoop helps dealerships protect that value by making core returns more timely and credit discrepancies easier to catch. We haven't solved every part of the circular-parts ecosystem yet, "
         "but we've built and tested the core decision engine that addresses one important part of it.'")

CLEAN = [
 "When a dealership replaces a part, the old component doesn't just become waste. In many cases it still has financial value, because the OEM can refund a core deposit when it is returned correctly and on time. Between removing the part, shipping it back and receiving the credit, there are several chances for that value to be lost. We built CoreLoop to help dealerships catch those problems before it's too late.",
 "A core return has a timeline: remove the part, ship it, wait for the OEM, receive the credit. There are three ways to lose the money: the part is never shipped or arrives late, the credit never arrives, or the credit is wrong or short. In our simulated ledger, a dealership that never checks loses $31,553; even a 90-day audit still loses $26,051.",
 "We simulated a dealership with 600 cores across three OEMs. On day 130 the planner found 42 cores waiting to ship and grouped them into three shipments instead of 42, respecting every deadline. Waiting one more day saves $11 of freight and puts two cores, $672 of deposits, out of reach.",
 "Not every late credit is a missing credit. In the first case a $140 credit never arrived; CoreLoop waited until the delay was clearly unusual for that OEM, then flagged it and drafted a dispute for a person to review. In the second, a credit was late but that OEM routinely takes a few extra days, so CoreLoop kept watching and the credit arrived. No false alarm. The price of that patience is that real misses are flagged about 20 days later, still before the dispute deadline.",
 "We automated the checks and kept the decisions with people. The top row is what to ship and when; the bottom row is what to do about a credit that has not arrived. Orange boxes are where a person decides. We deliberately did not automate filing disputes, $0 credits on damaged cores, or records that do not add up, because those are the cases where someone with the paperwork should decide.",
 "We tested four audit schedules plus no checking across 200 paired scenarios. Weekly auditing cut simulated loss from $26k to $4.3k. Continuous monitoring ended almost level with it, about $114 per ledger apart, with far less staff time and better resilience when audits get skipped. The best schedule depends on how quickly OEM windows expire.",
 "We looked at Tekion's public product information before defining our scope. Existing systems already manage parts and credits, so we are not replacing them. We focus on the decisions that connect them: when to ship, whether a return is at risk, and whether a credit needs attention. Not found means we could not see it, not that it does not exist.",
 "This is a short recording of the working prototype. We started with a simple question: what happens to the value of a part after it leaves the vehicle? CoreLoop helps dealerships protect that value by making core returns more timely and credit discrepancies easier to catch. We haven't solved every part of the circular-parts ecosystem, but we've built and tested the core decision engine for one important part of it.",
]
for sl, t in zip(prs.slides, CLEAN):
    sl.notes_slide.notes_text_frame.text = t

out = HERE / ("CoreLoop_Final_pdfmode.pptx" if os.environ.get("PDF_MODE") else "CoreLoop_Final.pptx")
prs.save(out)
print("saved", out)
