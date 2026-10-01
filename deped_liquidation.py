"""
DepEd School Liquidation Monitor v2  (Python 3.9+, standard library only)
Run: python deped_liquidation.py   |   Data: liquidation.db (same folder). See README.md.
Basis: DepEd Order 8 s.2019, DepEd Order 29 s.2019, COA-DBM-DepEd Joint Circular 2019-1.
"""
import csv, hashlib, html, os, secrets, shutil, sqlite3, sys, tkinter as tk, webbrowser
from datetime import date, datetime, timedelta
from tkinter import ttk, messagebox, filedialog, simpledialog

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
def _data_dir():
    base = os.environ.get("APPDATA") if os.name == "nt" else os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(base or os.path.expanduser("~"), "DepEdLiquidation"); os.makedirs(d, exist_ok=True); return d
DATA = _data_dir()
def res(name):  # find bundled resources (icon) both when run as a script and when packaged as .exe
    for base in (getattr(sys, "_MEIPASS", None), HERE):
        if base and os.path.exists(os.path.join(base, name)): return os.path.join(base, name)
if not os.path.exists(os.path.join(DATA, "liquidation.db")) and os.path.exists(os.path.join(HERE, "liquidation.db")):
    shutil.copy(os.path.join(HERE, "liquidation.db"), os.path.join(DATA, "liquidation.db"))  # carry over data from older versions
SOURCES = ["Regular MOOE Fund SHS", "Regular MOOE Fund JHS", "GAD Fund", "Canteen/Other School Fund", "SEF/Program Fund", "Other"]  # you can also type a new source
ALL = "All funds"
ACCOUNTS = [  # MOOE chart of accounts posted by the school (verify codes against your SDO's UACS list)
    ("Travel Expenses - Local", "50201010-00"), ("Training Expenses", "50202010-00"), ("Office Supplies Expenses", "50203010-00"),
    ("Food Supplies Expenses", "50203050-00"), ("Medical, Dental and Lab. Supplies Exp.", "50203080-00"), ("Drugs and Medicines Expenses", "10404060-00"),
    ("Fuel, Oil, and Lubricants Expenses", "50203090-00"), ("Other Supplies and Materials Expenses", "50203990-00"), ("Water Expenses", "50204010-00"),
    ("Electricity Expenses", "50204020-00"), ("Postage and Courier Expenses", "50205010-00"), ("Internet Subscription Expenses", "50205030-00"),
    ("Survey Expenses", "50207010-00"), ("Telephone Expenses- Mobile", "50205020-01"), ("Semi-Expendable Office Equipment Expenses", "50203210-03"),
    ("Semi-Expendable ICT Equipment Expenses", "50203080-00"), ("Semi-Expendable Furniture and Fixture Expenses", "50203220-01"),
    ("Repairs & Maintenance - Office Equipment", "50213050-02"), ("Repairs & Maintenance - Other Structure", "50213040-99"),
    ("Repairs & Maintenance - School Buildings", "50213040-03"), ("Repairs & Maintenance - ICT Equipment", "50213050-03"),
    ("Legal Services", "50211010-00"), ("Janitorial Services", "50212020-00"), ("Security Services", "50212030-00"), ("Fidelity Bond", "50215020-00"),
    ("Labor and Wages Expenses", "50216010-00"), ("Printing Publication Expenses", "50299020-02"), ("Transportation and Delivery Expense", "50299040-00"),
    ("Advances for Operating Expenses", "19901010-00"), ("Due to BIR", "20201010-00")]
CODE = dict(ACCOUNTS); CATEGORIES = [n for n, _ in ACCOUNTS]; LABELS = [f"{c} · {n}" for n, c in ACCOUNTS]
COA_DOC = "PO/docs received by COA (₱2,000 & above)"
LEGACY_DOCS = ["Disbursement Voucher", "Official Receipt/Invoice", "Purchase Request/Order or Contract", "Inspection/Acceptance Report", "Other supporting docs", COA_DOC]
# Mandatory attachments (revised MOOE List of Attachments) + the DV and check copy that every transaction type lists
MANDATORY = ["Cash/Check Disbursements Register (CDR)", "Statement of Account (SoA)", "Updated Check Ledger", "Annual Procurement Plan (APP)",
             "Market Scoping Form (Price Sourcing & Price Analysis)", "Project Procurement Management Plan (PPMP)", "Check Disbursement Voucher", "Photocopy of Check Issued"]
# Old document names from earlier versions -> current names (applied to saved records at startup)
RENAMED_DOCS = {"Cash Disbursements Register (CDR)": "Cash/Check Disbursements Register (CDR)", "Subsidiary Ledger": "Updated Check Ledger",
                "Disbursement Voucher (DV)": "Check Disbursement Voucher", "Authority to Travel / Locator Slip": "Approved Travel Order"}
RENAMED_TYPES = {"Hiring of Sound System / Venue": "Sound System Rental / Other Materials (no Official Receipt)", "Mobile Load": "Mobile Expenses"}
# Procurement modes (for purchase / repair-rehab-construction types)
PM_DA, PM_SVP, PM_SVPA = "Direct Acquisition", "Small Value Procurement - below ₱200,000", "Small Value Procurement - above ₱200,000"
PMODES = [PM_DA, PM_SVP, PM_SVPA]
# Rules: R = always required | O = optional / if applicable | 2K = required for ₱2,000 & above (tax documents)
#        SVP = required under Small Value Procurement | SVPA = required only for SVP above ₱200,000
X2K = [("Request for Quotation (price should be written)", "2K"), ("Abstract of Canvass (gross amount, not per item)", "2K"), ("Bids and Awards Committee (BAC Reso)", "2K"), ("BIR Form 2307", "2K")]
_OR = ("Official Receipt (OR) / Sales Invoice (purchased items should be written)", "R")
def _R(*names): return [(n, "R") for n in names]
PERMITS = _R("PhilGEPS Registration (not expired)", "BIR Registration (not expired)", "Mayor's Permit (not expired)", "DTI Permit (not expired)")
SVP_X = [("BAC Resolution – Employ", "SVP"), ("Canvass / RFQ", "SVP"), ("Opening of Canvass", "SVP"), ("Abstract of Bid as Read", "SVP"), ("BAC Resolution – Award", "SVP"),
         ("PhilGEPS Posting of Canvass / RFQ", "SVPA"), ("Notice of Award (NOA)", "SVPA"), ("Notice to Proceed (NTP)", "SVPA")]
SVP_BASE = _R("Purchase Request (PR)", "Contract of Service", "Job Order (received by COA – acknowledgement receipt)", "BAC Resolution – Employ", "Canvass / RFQ", "Opening of Canvass", "Abstract of Bid as Read", "BAC Resolution – Award")
_BUY = _R("Requisition and Issue Slip (RIS)", "Purchase Request (PR) – consolidated per project implementer", "Purchase Order (PO) – consolidated per project", "Certificate of Delivery",
          "Inspection & Acceptance Report (IAR) / Delivery Receipt", "Local Requisition and Issue Slip (LRIS)") + [("Inventory Custodian Slip (ICS) – non-consumable items", "O"), _OR] + _R("Picture of Items Purchased") + [("BIR Form 2307", "2K")] + PERMITS + [(COA_DOC, "2K")] + SVP_X
T_TRAVEL, T_SUPPLY, T_REPAIR, T_LABOR, T_ICT, T_JOB, T_UTIL, T_MOBILE, T_FOOD, T_HAUL, T_SOUND, T_FIDELITY = (
    "Travel Expenses", "Purchase of Office / School Supplies / Printing & Photocopy", "Repair / Rehab / Construction Supplies and Materials", "Labor",
    "Repairs of Office and/or ICT Equipments", "Jobbers / Watchman / School Aide", "Electricity / Water / Internet Bill", "Mobile Expenses",
    "Foods and Meals (Catering Services)", "Hauling Materials", "Sound System Rental / Other Materials (no Official Receipt)", "Fidelity Bond")
MODE_TYPES = {T_SUPPLY, T_REPAIR}
_LABOR = [("Approved Detailed Program of Works (POW)", "R")] + SVP_BASE + _R("Inspection & Acceptance Report (IAR)", "Acknowledgement Receipt", "Valid ID") + [("BIR Form 2307", "2K")]
CHECKLISTS = {
    T_TRAVEL: _R("Regional/Division/District Memo", "Approved Travel Order", "Itinerary of Travel (individual)", "Certificate of Travel Completed (CTC)") + [
        ("Locator Slip (less than one day)", "O"), ("Certificate of Expenses Not Requiring Receipt (CENRR) – ₱300 & below", "O"), ("Reimbursement Expenses Receipt (RER) – ₱301 to ₱1,000", "O"),
        ("Acknowledgment Receipt (AR) – ₱1,001 & above", "O"), ("Transportation & Terminal Fee Tickets (Airplane – Boarding Pass)", "O"), ("Official Receipt (OR) for Registration Fee", "O"),
        ("Certificate of Appearance, original copy (students' meals: Local ₱50, Region ₱50)", "O"), ("Payroll Breakdown of Student", "O"), ("Parent's Consent", "O"), ("Summary of Expenses of Student", "O")],
    T_SUPPLY: _BUY,
    T_REPAIR: [("Approved Detailed Program of Works (POW)", "R")] + _BUY,
    T_LABOR: _LABOR + _R("Labor Payroll", "Detailed Pictures (Before, During, After)"),
    T_ICT: [(n, "O" if n.startswith("Approved Detailed Program") else r) for n, r in _LABOR] + [("Labor Payroll", "O")] + _R("Waste Material Report (enumerated disposed materials)", "Picture (New & Broken Materials)"),
    T_JOB: _R("Approved Job Order / Contract of Service", "Daily Time Record (DTR)", "Accomplishment Report (per month)", "Acknowledgement Receipt (per month)", "Photocopy of Valid ID (not expired)", "Payroll"),
    T_UTIL: _R("SOA / Billing Statement", "Official Receipt (excluding surcharges)"),
    T_MOBILE: _R("Memorandum", "Requisition and Issue Slip (RIS)", "Purchase Request (PR)", "Purchase Order (PO)", "Certificate of Delivery (COD)", "Inspection and Acceptance Report (IAR)", "Local RIS",
                 "Official Receipt (per month)", "Certification (per month / signed PSDS)", "Duly signed DTR (per month / signed PSDS)") + [("Certificate of Travel Completed (if on official travel)", "O")],
    T_FOOD: _R("Activity / Budget / Project Proposal", "Menu", "Attendance", "Purchase Request (PR) – consolidated per project implementer", "Contract of Service – Catering", "Purchase Order (PO) – consolidated per project",
               "Certificate of Delivery", "Inspection & Acceptance Report (IAR)") + [_OR] + _R("MOVs / Picture of Items Purchased") + [("BIR Form 2307", "2K")] + PERMITS + [(COA_DOC, "2K")],
    T_HAUL: SVP_BASE + _R("Certificate of Delivery (COD)", "Inspection & Acceptance Report (IAR)", "Photocopy of Official Receipt (procured materials)") + [
        ("Certificate of Expenses Not Requiring Receipt (CENRR) – ₱300 & below", "O"), ("Reimbursement Expenses Receipt (RER) – ₱301 to ₱1,000", "O"), ("Acknowledgment Receipt (AR) – ₱1,001 & above", "O")] + _R(
        "Valid ID", "Pictures Showing the Actual Hauling of Materials"),
    T_SOUND: SVP_BASE + _R("Inspection & Acceptance Report (IAR)", "Acknowledgement Receipt (AR)", "Justification Letter for not Issuing Receipt (signed by Owner and School Head)",
                           "Barangay Certification of Non-Issuance of Official Receipt (with dry seal)", "Owner's Valid ID", "Owner's Barangay Permit", "Pictures"),
    T_FIDELITY: _R("Photocopy of Validated Deposit Slip", "Photocopy of ATAP", "Photocopy of Confirmation Letter") + [
        ("Application: BTR Application Form", "O"), ("Application: Notarized Application for Bonding", "O"), ("Application: Check Ledger – previous year (January to December)", "O"),
        ("Application: Previous BTR Confirmation Letter", "O"), ("Application: Designation Letter or Re-Assignment Order", "O"), ("Application: Passport-sized ID Picture", "O")],
}
DTYPES = list(CHECKLISTS)
# Types removed from the revised list: kept only so DVs already recorded under them still work (not offered in the dropdown)
CHECKLISTS.update({
    "School Teacher's ID": _R("Requisition and Issue Slip (RIS)", "Purchase Request (PR)", "Purchase Order (PO)", "Certificate of Delivery", "Local Requisition and Issue Slip (LRIS)", "Inspection Custodian Slip (ICS)") + [_OR] + _R("Picture of Items Purchased") + X2K + [(COA_DOC, "2K")],
    "Check Book": _R("Requisition and Issue Slip (write the series of the check book)", "Purchase Request (PR)", "Validated OR (DBP)"),
    "GAD Liquidation (Food / Venue / Supplies & Materials)": _R("Documents of the underlying Food / Venue / Supplies transaction attached"),
})
_P, _RP, _EW, _RO = T_SUPPLY, T_REPAIR, T_UTIL, T_ICT
SUGGEST = {"Travel Expenses - Local": T_TRAVEL, "Office Supplies Expenses": _P, "Food Supplies Expenses": T_FOOD, "Medical, Dental and Lab. Supplies Exp.": _P, "Drugs and Medicines Expenses": _P,
    "Fuel, Oil, and Lubricants Expenses": _P, "Other Supplies and Materials Expenses": _P, "Water Expenses": _EW, "Electricity Expenses": _EW, "Internet Subscription Expenses": _EW,
    "Telephone Expenses- Mobile": T_MOBILE, "Semi-Expendable Office Equipment Expenses": _P, "Semi-Expendable ICT Equipment Expenses": _P, "Semi-Expendable Furniture and Fixture Expenses": _P,
    "Repairs & Maintenance - Office Equipment": _RO, "Repairs & Maintenance - ICT Equipment": _RO, "Repairs & Maintenance - Other Structure": _RP, "Repairs & Maintenance - School Buildings": _RP,
    "Janitorial Services": T_JOB, "Security Services": T_JOB, "Fidelity Bond": T_FIDELITY, "Labor and Wages Expenses": T_LABOR, "Printing Publication Expenses": _P, "Transportation and Delivery Expense": T_HAUL}
def rule_on(rule, amt, pm=PM_DA):
    return rule == "R" or (rule == "2K" and amt >= 2000) or (rule == "SVP" and pm in (PM_SVP, PM_SVPA)) or (rule == "SVPA" and pm == PM_SVPA)
def all_docs(dt): return MANDATORY + [n for n, _ in CHECKLISTS[dt]] if dt in CHECKLISTS else LEGACY_DOCS
def req_docs(amt, dt="", pm=""):
    if dt not in CHECKLISTS: return LEGACY_DOCS[:4] + ([COA_DOC] if amt >= 2000 else [])
    return MANDATORY + [n for n, r in CHECKLISTS[dt] if rule_on(r, amt, pm if pm in PMODES and dt in MODE_TYPES else PM_DA)]
# School's posted tax guide (purchases & services of P2,000 and above): (VAT-registered?, first rate, second rate)
TAX = {"Goods - VAT": (True, .01, .05), "Services - VAT": (True, .02, .05), "Goods - Non-VAT": (False, .01, .03), "Services - Non-VAT": (False, .02, .03)}
TAXLIST = ["Not applicable / below ₱2,000"] + list(TAX); NOTAX = TAXLIST[0]
def calc_tax(kind, gross):
    if kind not in TAX: return 0.0, 0.0
    vat, r1, r2 = TAX[kind]; base = gross / 1.12 if vat else gross
    return round(base * r1, 2), round(base * r2, 2)
ROLES = ["School Head", "Bookkeeper"]
NAVY, NAVY2, GOLD, BG, CARD, LINE, INK, MUTE = "#0B1F3A", "#16305A", "#C9A227", "#F3F5F9", "#FFFFFF", "#DCE2EC", "#1B2A41", "#6B7A90"
RED, GREEN, AMBER = "#C0392B", "#1E8E5A", "#D98E04"
F = "Segoe UI"

db = sqlite3.connect(os.path.join(DATA, "liquidation.db"))
db.executescript("""
CREATE TABLE IF NOT EXISTS funds(id INTEGER PRIMARY KEY, name TEXT, source TEXT, ref_no TEXT, date_received TEXT, amount REAL, lr_due TEXT);
CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, fund_id INTEGER, dv_no TEXT, date TEXT, payee TEXT, particulars TEXT,
  category TEXT, amount REAL, doc_ref TEXT, docs TEXT DEFAULT '', lr_no TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT, hash TEXT, role TEXT);
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS caps(category TEXT PRIMARY KEY, pct REAL);
""")
for _c in ("fy INTEGER", "qtr INTEGER"):
    try: db.execute(f"ALTER TABLE funds ADD COLUMN {_c}")
    except sqlite3.OperationalError: pass
for _c in ("tax_type TEXT DEFAULT ''", "tax1 REAL DEFAULT 0", "tax2 REAL DEFAULT 0", "doc_type TEXT DEFAULT ''", "proc_mode TEXT DEFAULT ''"):
    try: db.execute(f"ALTER TABLE expenses ADD COLUMN {_c}")
    except sqlite3.OperationalError: pass
for _o, _n in RENAMED_TYPES.items(): db.execute("UPDATE expenses SET doc_type=? WHERE doc_type=?", (_n, _o))
for _i, _d in db.execute("SELECT id,docs FROM expenses WHERE docs<>''").fetchall():
    _new = "|".join(dict.fromkeys(RENAMED_DOCS.get(x, x) for x in _d.split("|")))
    if _new != _d: db.execute("UPDATE expenses SET docs=? WHERE id=?", (_new, _i))
db.execute("CREATE TABLE IF NOT EXISTS allocations(fy INTEGER, source TEXT, amount REAL, PRIMARY KEY(fy, source))")
db.execute("UPDATE funds SET fy=CAST(substr(date_received,1,4) AS INTEGER) WHERE fy IS NULL")
db.execute("UPDATE funds SET qtr=(CAST(substr(date_received,6,2) AS INTEGER)+2)/3 WHERE qtr IS NULL")
for _o, _n in {"Travelling Expenses": "Travel Expenses - Local", "Office Supplies": "Office Supplies Expenses", "Medical/Dental Supplies": "Medical, Dental and Lab. Supplies Exp.",
               "Water": "Water Expenses", "Electricity": "Electricity Expenses", "Postage/Courier": "Postage and Courier Expenses"}.items():
    db.execute("UPDATE expenses SET category=? WHERE category=?", (_n, _o)); db.execute("UPDATE OR IGNORE caps SET category=? WHERE category=?", (_n, _o))
db.commit()

def q(sql, *a): return db.execute(sql, a).fetchall()
def money(x): return f"{x:,.2f}"
def setting(k, d=""):
    r = q("SELECT v FROM settings WHERE k=?", k); return r[0][0] if r else d
def put(k, v): db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v)); db.commit()
def pdate(s):
    try: return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError: return None
def due_date(d):
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return nxt + timedelta(days=int(setting("lr_days", "15") or 15) - 1)
def hpw(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
def num(s):
    try: return float(s.replace(",", ""))
    except ValueError: return 0.0

# ---------- UI helpers ----------
def center(win, w=None, h=None):
    """Place a window in the middle of the screen (optionally at a fixed size)."""
    win.update_idletasks(); w = w or win.winfo_reqwidth(); h = h or win.winfo_reqheight()
    x, y = max((win.winfo_screenwidth() - w) // 2, 0), max((win.winfo_screenheight() - h) // 2 - 20, 0)
    win.geometry(f"{w}x{h}+{x}+{y}" if (w, h) != (win.winfo_reqwidth(), win.winfo_reqheight()) else f"+{x}+{y}")
def button(parent, text, cmd, kind="gold"):
    bg, fg = {"gold": (GOLD, NAVY), "navy": (NAVY, "white"), "red": (RED, "white")}[kind]
    b = tk.Label(parent, text=text, bg=bg, fg=fg, font=(F, 10, "bold"), padx=16, pady=8, cursor="hand2")
    b.bind("<Button-1>", lambda e: cmd()); b.bind("<Enter>", lambda e: b.config(bg=NAVY2 if kind == "navy" else "#DDB93A" if kind == "gold" else "#A93226"))
    b.bind("<Leave>", lambda e: b.config(bg=bg)); return b
def card(parent, title=None):
    c = tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1)
    if title: tk.Label(c, text=title, bg=CARD, fg=NAVY, font=(F, 11, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
    return c
def inner(c):
    g = tk.Frame(c, bg=CARD); g.pack(fill="x"); return g
def field(parent, r, c, label, var, opts=None, ro=False, w=22):
    tk.Label(parent, text=label, bg=CARD, fg=MUTE, font=(F, 9)).grid(row=r * 2, column=c, sticky="w", padx=(14, 6), pady=(8, 0))
    wd = ttk.Combobox(parent, textvariable=var, values=opts or [], width=w, state="readonly" if ro else "normal") if opts is not None \
        else ttk.Entry(parent, textvariable=var, width=w + 2)
    wd.grid(row=r * 2 + 1, column=c, sticky="w", padx=(14, 6), pady=(0, 4)); return wd
def table(parent, cols, widths=None, h=10):
    f = tk.Frame(parent, bg=CARD); t = ttk.Treeview(f, columns=cols, show="headings", height=h)
    for c in cols: t.heading(c, text=c); t.column(c, width=(widths or {}).get(c, 110), anchor="w")
    sb = ttk.Scrollbar(f, command=t.yview); t.configure(yscrollcommand=sb.set)
    t.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
    for tag, col in (("bad", "#FBE3E0"), ("warn", "#FFF3CF"), ("ok", "#E1F4EA")): t.tag_configure(tag, background=col)
    return f, t

def _logo_path(only_school=False):
    for p in (os.path.join(DATA, "deped_logo.png"), res("deped_logo.png")) + (() if only_school else (res("app.png"),)):
        if p and os.path.exists(p): return p
def logo_image(max_px):
    """The school's DepEd logo if deped_logo.png is supplied (app folder or data folder), else the app icon."""
    p = _logo_path()
    if not p: return None
    try:
        try:
            from PIL import Image, ImageTk
            im = Image.open(p).convert("RGBA"); im.thumbnail((max_px, max_px), Image.LANCZOS); return ImageTk.PhotoImage(im)
        except ImportError:
            img = tk.PhotoImage(file=p); f = max(1, -(-max(img.width(), img.height()) // max_px)); return img.subsample(f) if f > 1 else img
    except Exception: return None
def logo_b64():
    import base64
    p = _logo_path(True)
    return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode() if p else ""

class Login(tk.Toplevel):
    def __init__(self, root):
        super().__init__(root); self.root = root; self.title("Sign in"); self.configure(bg=NAVY)
        center(self, 520, 690); self.resizable(False, False); self.first = not q("SELECT 1 FROM users")
        self.logo = logo_image(170)
        if self.logo: tk.Label(self, image=self.logo, bg=NAVY).pack(pady=(34, 6))
        tk.Label(self, text="DepEd", font=(F, 36, "bold"), fg=GOLD, bg=NAVY).pack(pady=(0 if self.logo else 40, 0))
        tk.Label(self, text="SCHOOL LIQUIDATION MONITOR", font=(F, 11, "bold"), fg="#9FB3D1", bg=NAVY).pack()
        tk.Frame(self, bg=GOLD, height=3, width=90).pack(pady=16)
        tk.Label(self, text="Create the School Head account" if self.first else "Sign in to continue", fg="white", bg=NAVY, font=(F, 13)).pack(pady=(0, 14))
        self.u, self.p = tk.StringVar(), tk.StringVar()
        for lbl, v, sh in (("Username", self.u, ""), ("Password", self.p, "•")):
            tk.Label(self, text=lbl, fg="#9FB3D1", bg=NAVY, font=(F, 10)).pack(anchor="w", padx=80)
            tk.Entry(self, textvariable=v, show=sh, font=(F, 13), relief="flat").pack(padx=80, pady=(3, 14), ipady=9, fill="x")
        b_ = button(self, "Create account" if self.first else "Sign in", self.go); b_.config(padx=70, pady=13, font=(F, 12, "bold")); b_.pack(pady=10)
        self.msg = tk.Label(self, text="", fg="#FF9E92", bg=NAVY, font=(F, 10)); self.msg.pack()
        self.bind("<Return>", lambda e: self.go()); self.protocol("WM_DELETE_WINDOW", root.destroy); self.grab_set()
    def go(self):
        u, p = self.u.get().strip(), self.p.get()
        if self.first:
            if not u or len(p) < 6: return self.msg.config(text="Username required; password min. 6 characters.")
            s = secrets.token_hex(16); db.execute("INSERT INTO users VALUES(?,?,?,?)", (u, s, hpw(p, s), "School Head")); db.commit()
            self.root.user = (u, "School Head")
        else:
            r = q("SELECT salt,hash,role FROM users WHERE username=?", u)
            if not r or hpw(p, r[0][0]) != r[0][1]: return self.msg.config(text="Incorrect username or password.")
            self.root.user = (u, r[0][2])
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.withdraw(); self.user = None; self.set_icon()
        self.wait_window(Login(self))
        if not self.user: return self.destroy()
        self.deiconify(); self.title("DepEd School Liquidation Monitor"); center(self, min(1240, self.winfo_screenwidth() - 60), min(760, self.winfo_screenheight() - 100)); self.minsize(1100, 680); self.configure(bg=BG)
        st = ttk.Style(self); st.theme_use("clam")
        st.configure("Treeview", rowheight=30, font=(F, 10), background=CARD, fieldbackground=CARD, borderwidth=0, foreground=INK)
        st.configure("Treeview.Heading", font=(F, 9, "bold"), background=NAVY, foreground="white", relief="flat", padding=8)
        st.map("Treeview.Heading", background=[("active", NAVY2)]); st.map("Treeview", background=[("selected", "#CFE0FA")], foreground=[("selected", NAVY)])
        st.configure("TCombobox", padding=4); st.configure("TEntry", padding=5)
        side = tk.Frame(self, bg=NAVY, width=220); side.pack(side="left", fill="y"); side.pack_propagate(False)
        self.side_logo = logo_image(58)
        if self.side_logo: tk.Label(side, image=self.side_logo, bg=NAVY).pack(anchor="w", padx=22, pady=(22, 0))
        tk.Label(side, text="DepEd", font=(F, 22, "bold"), fg=GOLD, bg=NAVY).pack(anchor="w", padx=22, pady=(8 if self.side_logo else 26, 0))
        tk.Label(side, text="Liquidation Monitor", font=(F, 10), fg="#9FB3D1", bg=NAVY).pack(anchor="w", padx=22, pady=(0, 24))
        main = tk.Frame(self, bg=BG); main.pack(side="left", fill="both", expand=True)
        head = tk.Frame(main, bg=CARD, highlightbackground=LINE, highlightthickness=1); head.pack(fill="x")
        self.title_l = tk.Label(head, font=(F, 16, "bold"), fg=NAVY, bg=CARD); self.title_l.pack(side="left", padx=24, pady=14)
        tk.Label(head, text=f"{self.user[0]}  ·  {self.user[1]}", font=(F, 10), fg=MUTE, bg=CARD).pack(side="right", padx=24)
        self.body = tk.Frame(main, bg=BG); self.body.pack(fill="both", expand=True, padx=24, pady=18)
        pages = [("Dashboard", self.p_dash), ("Funds Received", self.p_funds), ("Expenses / DVs", self.p_exp), ("Liquidation Report", self.p_lr)]
        if self.user[1] == "School Head": pages.append(("Settings", self.p_set))
        self.pages, self.nav = {}, {}
        for name, build in pages:
            fr = tk.Frame(self.body, bg=BG); build(fr); self.pages[name] = fr
            l = tk.Label(side, text="   " + name, anchor="w", font=(F, 11), fg="#C7D3E8", bg=NAVY, pady=11, cursor="hand2")
            l.pack(fill="x"); l.bind("<Button-1>", lambda e, n=name: self.show(n)); self.nav[name] = l
        tk.Label(side, text="Confidential · school use", font=(F, 8), fg="#6F86A8", bg=NAVY).pack(side="bottom", pady=14)
        self.show("Dashboard")

    def set_icon(self):
        try:
            if os.name == "nt":
                import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DepEd.LiquidationMonitor")  # own taskbar icon
                if res("app.ico"): self.iconbitmap(default=res("app.ico"))
            if res("app.png"): self._icon = tk.PhotoImage(file=res("app.png")); self.iconphoto(True, self._icon)
        except Exception: pass
    def show(self, name):
        for n, f in self.pages.items(): f.pack_forget(); self.nav[n].config(bg=NAVY, fg="#C7D3E8", font=(F, 11))
        self.pages[name].pack(fill="both", expand=True); self.nav[name].config(bg=NAVY2, fg=GOLD, font=(F, 11, "bold"))
        self.title_l.config(text=name); self.refresh()

    def fund_names(self): return [f"{r[0]} | {r[1]}" for r in q("SELECT id,name FROM funds ORDER BY id DESC")]
    def fid(self, s): return int(s.split("|")[0]) if s else None
    def stats(self, fid):
        rec = q("SELECT amount FROM funds WHERE id=?", fid)[0][0]
        sp = q("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE fund_id=?", fid)[0][0]
        lq = q("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE fund_id=? AND lr_no<>''", fid)[0][0]
        return rec, sp, lq

    # ----- Dashboard -----
    def p_dash(self, p):
        top = tk.Frame(p, bg=BG); top.pack(fill="x", pady=(0, 10)); self.dfilter = tk.StringVar(value=ALL)
        tk.Label(top, text="Show:", bg=BG, fg=MUTE, font=(F, 10)).pack(side="left"); cb = ttk.Combobox(top, textvariable=self.dfilter, values=[ALL] + SOURCES, state="readonly", width=32); cb.pack(side="left", padx=8); self.dcb = cb
        self.dyear, self.dqtr = tk.StringVar(value="All years"), tk.StringVar(value="All quarters")
        self.dycb = ttk.Combobox(top, textvariable=self.dyear, values=["All years"], state="readonly", width=10); self.dycb.pack(side="left", padx=(10, 0))
        qcb = ttk.Combobox(top, textvariable=self.dqtr, values=["All quarters", "Q1", "Q2", "Q3", "Q4"], state="readonly", width=13); qcb.pack(side="left", padx=8)
        for w_ in (cb, self.dycb, qcb): w_.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        button(top, "Clear filters", lambda: (self.dfilter.set(ALL), self.dyear.set("All years"), self.dqtr.set("All quarters"), self.refresh()), "navy").pack(side="left", padx=8)
        row = tk.Frame(p, bg=BG); row.pack(fill="x"); self.kpi = {}
        for i, (k, col) in enumerate((("Released to School", NAVY), ("Disbursed (incl. tax)", GOLD), ("Unliquidated", AMBER), ("Balance", GREEN), ("Tax Withheld (Due to BIR)", "#6C4AB6"))):
            c = card(row); c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 12, 0)); row.columnconfigure(i, weight=1)
            tk.Frame(c, bg=col, height=4).pack(fill="x")
            tk.Label(c, text=k.upper(), font=(F, 8, "bold"), fg=MUTE, bg=CARD).pack(anchor="w", padx=16, pady=(12, 0))
            self.kpi[k] = tk.Label(c, text="₱0.00", font=(F, 17, "bold"), fg=NAVY, bg=CARD); self.kpi[k].pack(anchor="w", padx=16, pady=(0, 14))
        c = card(p, "Fund status"); c.pack(fill="x", pady=14)
        cols = ("Fund", "Received", "Disbursed", "Unliquidated", "Balance", "% Used", "LR Due", "Status")
        f, self.dt = table(c, cols, {"Fund": 230, "Status": 220}, 6); f.pack(fill="x", padx=12, pady=(4, 12))
        bot = tk.Frame(p, bg=BG); bot.pack(fill="both", expand=True); bot.columnconfigure((0, 1), weight=1, uniform="a"); bot.rowconfigure(0, weight=1)
        a = card(bot, "Alerts — act on these first"); a.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.alerts = tk.Listbox(a, font=(F, 10), relief="flat", bd=0, highlightthickness=0, activestyle="none", bg=CARD, fg=INK); self.alerts.pack(fill="both", expand=True, padx=12, pady=(2, 12))
        b = card(bot, "Spending by category (share of funds released; red = over cap)"); b.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.cv = tk.Canvas(b, bg=CARD, highlightthickness=0, height=200); self.cv.pack(fill="both", expand=True, padx=8, pady=(2, 10)); self.cv.bind("<Configure>", lambda e: self.bars())

    def flt(self):
        c, a = [], []
        if self.dfilter.get() != ALL: c.append("source=?"); a.append(self.dfilter.get())
        if self.dyear.get() != "All years": c.append("fy=?"); a.append(int(self.dyear.get()))
        if self.dqtr.get() != "All quarters": c.append("qtr=?"); a.append(int(self.dqtr.get()[1]))
        return ("WHERE " + " AND ".join(c) if c else "", tuple(a))
    def bars(self):
        fw, fa = self.flt()
        c = self.cv; c.delete("all"); w = max(c.winfo_width(), 420); y = 10
        tot = q(f"SELECT category,SUM(amount-tax1-tax2) FROM expenses WHERE fund_id IN (SELECT id FROM funds {fw}) GROUP BY category", *fa)
        tb = q(f"SELECT COALESCE(SUM(tax1+tax2),0) FROM expenses WHERE fund_id IN (SELECT id FROM funds {fw})", *fa)[0][0]
        tot = sorted(tot + ([("Due to BIR", tb)] if tb else []), key=lambda x: -x[1])[:8]
        rec = q(f"SELECT COALESCE(SUM(amount),0) FROM funds {fw}", *fa)[0][0]; caps = dict(q("SELECT category,pct FROM caps"))
        if not tot: c.create_text(12, 20, text="No expenses yet.", anchor="w", fill=MUTE, font=(F, 10))
        x0, bw = 200, w - 200 - 110
        for cat, a in tot:
            pct = a / rec if rec else 0; cap = caps.get(cat, 0) or 0
            c.create_text(8, y + 9, text=cat, anchor="w", font=(F, 9), fill=INK)
            c.create_rectangle(x0, y, x0 + bw, y + 18, fill="#E8ECF4", outline="")
            c.create_rectangle(x0, y, x0 + bw * min(pct, 1), y + 18, fill=RED if cap and pct * 100 > cap else GOLD, outline="")
            if cap: c.create_line(x0 + bw * cap / 100, y - 3, x0 + bw * cap / 100, y + 21, fill=NAVY, width=2)
            c.create_text(x0 + bw + 8, y + 9, text=f"{money(a)}", anchor="w", font=(F, 9), fill=MUTE); y += 26

    def r_dash(self):
        self.dt.delete(*self.dt.get_children()); self.alerts.delete(0, "end"); today = date.today(); T = [0, 0, 0]
        w, a = self.flt()
        for fid, name, due in q(f"SELECT id,name,lr_due FROM funds {w} ORDER BY id DESC", *a):
            rec, sp, lq = self.stats(fid); un, bal = sp - lq, rec - sp; T[0] += rec; T[1] += sp; T[2] += un
            dd = pdate(due or ""); tag, s = "ok", "On track"
            if un > 0 and dd and today > dd: tag, s = "bad", f"OVERDUE {(today - dd).days} day(s)"; self.alerts.insert("end", f"⛔  OVERDUE · {name}: {money(un)} unliquidated (due {due})")
            elif un > 0 and dd and (dd - today).days <= 5: tag, s = "warn", f"Due in {(dd - today).days} day(s)"; self.alerts.insert("end", f"⚠  DUE SOON · {name}: {money(un)} (due {due})")
            if bal < 0: tag, s = "bad", "OVERSPENT"
            elif rec and bal / rec < 0.1: self.alerts.insert("end", f"⚠  LOW BALANCE · {name}: {money(bal)} left")
            self.dt.insert("", "end", tags=(tag,), values=(name, money(rec), money(sp), money(un), money(bal), f"{sp / rec * 100 if rec else 0:.1f}%", due, s))
        for dv, docs, amt, dt, pm in q(f"SELECT dv_no,docs,amount,doc_type,proc_mode FROM expenses WHERE lr_no='' AND fund_id IN (SELECT id FROM funds {w})", *a):
            gap = [d for d in req_docs(amt, dt, pm) if d not in docs.split("|")]
            if gap: self.alerts.insert("end", f"📎  INCOMPLETE DOCS · DV {dv}: missing {', '.join(gap)}")
        if not self.alerts.size(): self.alerts.insert("end", "✓  All clear — no pending alerts.")
        for k, v in zip(self.kpi, (T[0], T[1], T[2], T[0] - T[1], q(f"SELECT COALESCE(SUM(tax1+tax2),0) FROM expenses WHERE fund_id IN (SELECT id FROM funds {w})", *a)[0][0])): self.kpi[k].config(text="₱" + money(v))
        self.bars()

    # ----- Funds (released quarterly by the SDO) -----
    def p_funds(self, p):
        a = inner(card(p, "Annual allocation (from the SDO's written notice) vs. quarterly releases")); a.master.pack(fill="x")
        self.av = {k: tk.StringVar() for k in ("fy", "src", "amt")}; self.av["fy"].set(str(date.today().year)); self.av["src"].set(SOURCES[0])
        field(a, 0, 0, "Fiscal year", self.av["fy"], w=8); self.src_cb1 = field(a, 0, 1, "Fund source (type to add new)", self.av["src"], SOURCES, False, 28); field(a, 0, 2, "Annual allocation (₱)", self.av["amt"])
        button(a, "Save allocation", self.set_alloc).grid(row=1, column=3, sticky="sw", padx=14, pady=(0, 6))
        f0, self.at = table(a.master, ("Year", "Source", "Annual Allocation", "Released so far", "Still to be released", "Quarters received"), {"Year": 70, "Source": 200, "Quarters received": 200}, 3); f0.pack(fill="x", padx=12, pady=(0, 12))
        c = inner(card(p, "Record a quarterly release / cash advance from the SDO")); c.master.pack(fill="x", pady=(12, 0))
        self.fv = {k: tk.StringVar() for k in ("fy", "qtr", "src", "name", "ref", "date", "amt", "due")}
        self.fv["fy"].set(str(date.today().year)); self.fv["qtr"].set(f"Q{(date.today().month - 1) // 3 + 1}"); self.fv["src"].set(SOURCES[0]); self.fv["date"].set(str(date.today()))
        field(c, 0, 0, "Fiscal year", self.fv["fy"], w=8); field(c, 0, 1, "Quarter", self.fv["qtr"], ["Q1", "Q2", "Q3", "Q4"], True, 8)
        self.src_cb2 = field(c, 0, 2, "Fund source (type to add new)", self.fv["src"], SOURCES, False, 28); field(c, 0, 3, "Fund name (blank = auto)", self.fv["name"])
        field(c, 1, 0, "SDO ref / DV / check no.", self.fv["ref"]); field(c, 1, 1, "Date received (YYYY-MM-DD)", self.fv["date"])
        field(c, 1, 2, "Amount released (₱)", self.fv["amt"]); field(c, 1, 3, "LR due date (blank = auto)", self.fv["due"])
        button(c, "＋  Add quarterly release", self.add_fund).grid(row=3, column=0, sticky="w", padx=14, pady=12)
        c2 = card(p); c2.pack(fill="both", expand=True, pady=14)
        f, self.ft = table(c2, ("ID", "Year", "Qtr", "Name", "Source", "Ref", "Date", "Amount", "LR Due"), {"ID": 45, "Year": 60, "Qtr": 50, "Name": 220, "Source": 180}, 5); f.pack(fill="both", expand=True, padx=12, pady=12)
        if self.user[1] == "School Head": button(p, "Delete selected release", self.del_fund, "red").pack(anchor="e")

    def set_alloc(self):
        fy, amt = int(num(self.av["fy"].get())), num(self.av["amt"].get())
        if not 2000 <= fy <= 2100 or amt <= 0 or not self.av["src"].get().strip(): return messagebox.showerror("Check input", "Enter a fund source, a valid fiscal year and an amount > 0.")
        db.execute("INSERT OR REPLACE INTO allocations VALUES(?,?,?)", (fy, self.av["src"].get().strip(), amt)); db.commit(); self.av["amt"].set(""); self.refresh()

    def add_fund(self):
        v = {k: x.get().strip() for k, x in self.fv.items()}; d = pdate(v["date"]); amt = num(v["amt"]); fy = int(num(v["fy"]))
        if not 2000 <= fy <= 2100 or not d or amt <= 0 or not v["src"]: return messagebox.showerror("Check input", "A fund source, valid fiscal year, date and amount > 0 are required.")
        qn = int(v["qtr"][1]); name = v["name"] or f"{v['src']} · {v['qtr']} {fy}"
        if q("SELECT 1 FROM funds WHERE fy=? AND qtr=? AND source=?", fy, qn, v["src"]) and not messagebox.askyesno("Already recorded", f"A {v['qtr']} {fy} release for {v['src']} already exists.\nAdd another (e.g. a supplemental release)?"): return
        al = (q("SELECT amount FROM allocations WHERE fy=? AND source=?", fy, v["src"]) or [[0]])[0][0]
        rel = q("SELECT COALESCE(SUM(amount),0) FROM funds WHERE fy=? AND source=?", fy, v["src"])[0][0]
        if al and rel + amt > al and not messagebox.askyesno("Above annual allocation", f"Releases would total ₱{money(rel + amt)}, above the ₱{money(al)} annual allocation.\nRecord anyway?"): return
        db.execute("INSERT INTO funds(name,source,ref_no,date_received,amount,lr_due,fy,qtr) VALUES(?,?,?,?,?,?,?,?)", (name, v["src"], v["ref"], v["date"], amt, v["due"] or str(due_date(d)), fy, qn)); db.commit()
        for k in ("name", "ref", "amt", "due"): self.fv[k].set("")
        self.refresh()

    def r_funds(self):
        self.ft.delete(*self.ft.get_children()); self.at.delete(*self.at.get_children())
        for r in q("SELECT id,fy,qtr,name,source,ref_no,date_received,amount,lr_due FROM funds ORDER BY fy DESC,qtr DESC,id DESC"): self.ft.insert("", "end", values=(r[0], r[1], f"Q{r[2]}", *r[3:7], money(r[7]), r[8]))
        for fy, src in sorted(set(q("SELECT fy,source FROM funds")) | set((a, b) for a, b, _ in q("SELECT * FROM allocations")), reverse=True):
            al = (q("SELECT amount FROM allocations WHERE fy=? AND source=?", fy, src) or [[0]])[0][0]
            rel = q("SELECT COALESCE(SUM(amount),0) FROM funds WHERE fy=? AND source=?", fy, src)[0][0]
            qs = ", ".join(f"Q{n}" for (n,) in q("SELECT DISTINCT qtr FROM funds WHERE fy=? AND source=? ORDER BY qtr", fy, src)) or "none yet"
            self.at.insert("", "end", tags=("bad",) if al and rel > al else (), values=(fy, src, money(al) if al else "not set", money(rel), money(al - rel) if al else "—", qs))
    def del_fund(self):
        s = self.ft.selection()
        if s and messagebox.askyesno("Confirm", "Delete this fund and ALL its expenses?"):
            i = self.ft.item(s[0])["values"][0]; db.execute("DELETE FROM expenses WHERE fund_id=?", (i,)); db.execute("DELETE FROM funds WHERE id=?", (i,)); db.commit(); self.refresh()

    # ----- Expenses -----
    def p_exp(self, p):
        c = inner(card(p, "Record disbursement — one row per paid DV")); c.master.pack(fill="x")
        self.ev = {k: tk.StringVar() for k in ("fund", "dv", "date", "payee", "part", "cat", "amt", "ref", "tax", "dtype", "pmode")}; self.ev["tax"].set(NOTAX); self.ev["pmode"].set(PM_DA); self.ev["date"].set(str(date.today())); self.ev["cat"].set(LABELS[0])
        self.fund_cb = field(c, 0, 0, "Fund", self.ev["fund"], [], True); field(c, 0, 1, "DV no.", self.ev["dv"]); field(c, 0, 2, "Date (YYYY-MM-DD)", self.ev["date"]); field(c, 0, 3, "Payee", self.ev["payee"])
        field(c, 1, 0, "Particulars", self.ev["part"]); field(c, 1, 1, "Account (UACS code · name)", self.ev["cat"], LABELS, True, 34); field(c, 1, 2, "Amount (₱)", self.ev["amt"]); field(c, 1, 3, "OR / Invoice no.", self.ev["ref"])
        field(c, 2, 0, "Tax type (purchases & services ₱2,000+)", self.ev["tax"], TAXLIST, True, 30)
        self.taxlbl = tk.Label(c, text="", bg=CARD, fg=NAVY, font=(F, 10, "bold")); self.taxlbl.grid(row=6, column=0, columnspan=4, sticky="w", padx=14)
        for k in ("amt", "tax"): self.ev[k].trace_add("write", lambda *a: self.tax_preview())
        field(c, 2, 1, "Transaction type (DepEd supporting-documents checklist)", self.ev["dtype"], DTYPES, True, 46)
        button(c, "📎  Supporting documents…", self.form_docs, "navy").grid(row=5, column=2, sticky="sw", padx=14, pady=(0, 4))
        self.doclbl = tk.Label(c, text="", bg=CARD, font=(F, 9, "bold")); self.doclbl.grid(row=5, column=3, sticky="sw", padx=8, pady=(0, 8))
        field(c, 4, 0, "Procurement mode (supplies / repair types)", self.ev["pmode"], PMODES, True, 34); self.ev["pmode"].trace_add("write", lambda *a: self.doc_summary())
        self.cur_docs = set(); self.ev["dtype"].set(SUGGEST.get(CATEGORIES[0], ""))
        self.ev["cat"].trace_add("write", lambda *a: self.suggest_type()); self.ev["amt"].trace_add("write", lambda *a: self.doc_summary())
        self.ev["dtype"].trace_add("write", lambda *a: (setattr(self, "cur_docs", set()), self.doc_summary())); self.doc_summary()
        button(c, "＋  Add expense", self.add_exp).grid(row=10, column=0, sticky="w", padx=14, pady=12)
        c2 = card(p); c2.pack(fill="both", expand=True, pady=14)
        f, self.et = table(c2, ("ID", "Fund", "DV", "Date", "Payee", "Category", "UACS Code", "Transaction Amt", "Less: Tax", "Net Expense", "Docs", "LR No."), {"ID": 40, "Fund": 150, "Payee": 150, "Category": 210, "UACS Code": 100, "LR No.": 130}, 9); f.pack(fill="both", expand=True, padx=12, pady=12)
        bt = tk.Frame(p, bg=BG); bt.pack(fill="x")
        button(bt, "✔  Mark selected as liquidated", self.mark_liq).pack(side="left"); button(bt, "📎  Update documents", self.edit_docs, "navy").pack(side="left", padx=10); button(bt, "🖨  Print selected liquidated", self.print_selected, "navy").pack(side="left", padx=(0, 10))
        if self.user[1] == "School Head": button(bt, "↩  Undo liquidation", self.undo_liq, "navy").pack(side="left")
        button(bt, "Delete selected (unliquidated only)", self.del_exp, "red").pack(side="right")

    def tax_preview(self):
        g = num(self.ev["amt"].get()); t1, t2 = calc_tax(self.ev["tax"].get(), g)
        self.taxlbl.config(text=f"Transaction ₱{money(g)}  −  tax withheld ₱{money(t1 + t2)} (income tax ₱{money(t1)} + VAT/percentage tax ₱{money(t2)})  =  net expense ₱{money(g - t1 - t2)}   ·   tax goes under Due to BIR" if t1 + t2
                           else "Tax guide applies: choose a tax type." if g >= 2000 else "")
    def add_exp(self):
        e = {k: x.get().strip() for k, x in self.ev.items()}; amt = num(e["amt"]); e["cat"] = e["cat"].split(" · ", 1)[-1]
        if not e["fund"]: return messagebox.showerror("Check input", "Create and select a fund first.")
        if not e["dv"] or not pdate(e["date"]) or amt <= 0: return messagebox.showerror("Check input", "DV no., a valid date and amount > 0 are required.")
        if not e["dtype"]: return messagebox.showerror("Check input", "Choose the transaction type (it sets the required supporting documents).")
        if amt >= 2000 and e["tax"] not in TAX and not messagebox.askyesno("No tax type selected", "Purchases and services of ₱2,000 and above normally need tax withheld per your posted guide.\nRecord without tax anyway?"): return
        t1, t2 = calc_tax(e["tax"], amt); ttype = e["tax"] if e["tax"] in TAX else ""
        fid = self.fid(e["fund"]); rec, sp, _ = self.stats(fid)
        if sp + amt > rec: return messagebox.showerror("Blocked", f"Exceeds available balance of ₱{money(rec - sp)}.\nDisbursements cannot exceed funds received.")
        if q("SELECT 1 FROM expenses WHERE dv_no=? AND fund_id=?", e["dv"], fid): return messagebox.showerror("Duplicate", "This DV number already exists in this fund.")
        cap = (q("SELECT pct FROM caps WHERE category=?", e["cat"]) or [[0]])[0][0]
        if cap:
            used = q("SELECT COALESCE(SUM(amount-tax1-tax2),0) FROM expenses WHERE fund_id=? AND category=?", fid, e["cat"])[0][0]; net = amt - t1 - t2
            if used + net > rec * cap / 100 and not messagebox.askyesno("Category cap exceeded", f"{e['cat']} would reach ₱{money(used + net)}, above the {cap:g}% cap (₱{money(rec * cap / 100)}).\nRecord anyway?"): return
        db.execute("INSERT INTO expenses(fund_id,dv_no,date,payee,particulars,category,amount,doc_ref,docs,tax_type,tax1,tax2,doc_type,proc_mode) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (fid, e["dv"], e["date"], e["payee"], e["part"], e["cat"], amt, e["ref"], "|".join(n for n in all_docs(e["dtype"]) if n in self.cur_docs), ttype, t1, t2, e["dtype"], e["pmode"] if e["dtype"] in MODE_TYPES else "")); db.commit()
        for k in ("dv", "payee", "part", "amt", "ref"): self.ev[k].set("")
        self.ev["tax"].set(NOTAX)
        self.cur_docs = set(); self.doc_summary()
        self.refresh()
    def sel_ids(self): return [self.et.item(i)["values"][0] for i in self.et.selection()]
    def mark_liq(self):
        ids = [i for i in self.sel_ids() if not q("SELECT lr_no FROM expenses WHERE id=?", i)[0][0]]
        if not ids: return messagebox.showinfo("Select DVs", "Select one or more unliquidated expenses first (Ctrl+click or Shift+click to pick several).")
        lr = self.ask_text("Mark as liquidated", f"{len(ids)} DV(s) selected.\nEnter the LR number or reference (e.g. date submitted):", f"LR-{date.today():%Y%m%d}")
        if not lr or not lr.strip(): return
        bad = sum(not all(d in docs.split("|") for d in req_docs(amt, dt, pm)) for amt, docs, dt, pm in (q("SELECT amount,docs,doc_type,proc_mode FROM expenses WHERE id=?", i)[0] for i in ids))
        if bad and not messagebox.askyesno("Incomplete documents", f"{bad} of {len(ids)} selected DV(s) are missing required documents.\nMark as liquidated anyway?"): return
        db.executemany("UPDATE expenses SET lr_no=? WHERE id=?", [(lr.strip(), i) for i in ids]); db.commit(); self.refresh()
    def suggest_type(self):
        n = self.ev["cat"].get().split(" · ", 1)[-1]
        if n in SUGGEST and self.ev["dtype"].get() != SUGGEST[n]: self.ev["dtype"].set(SUGGEST[n])
    def doc_summary(self):
        need = req_docs(num(self.ev["amt"].get()), self.ev["dtype"].get(), self.ev["pmode"].get()); ok = sum(d in self.cur_docs for d in need)
        self.doclbl.config(text=f"{ok}/{len(need)} required documents ticked", fg=GREEN if ok == len(need) else AMBER)
    def form_docs(self):
        if not self.ev["dtype"].get(): return messagebox.showinfo("Choose a type", "Select the transaction type first.")
        def save(dt, ticked, pm): self.cur_docs = ticked; self.ev["pmode"].set(pm); self.doc_summary()
        self.docs_dialog("Supporting documents", self.ev["dtype"].get(), num(self.ev["amt"].get()), self.cur_docs, save, lock_type=True, pm=self.ev["pmode"].get())
    def docs_dialog(self, title, dt, amt, have, on_save, lock_type=False, pm=""):
        win = tk.Toplevel(self); win.withdraw(); win.title(title); win.configure(bg=CARD); win.transient(self); dtv = tk.StringVar(value=dt); pmv = tk.StringVar(value=pm if pm in PMODES else PM_DA); vs = {}
        top = tk.Frame(win, bg=CARD); top.pack(fill="x", padx=18, pady=(14, 0)); tk.Label(top, text="Transaction type:", bg=CARD, fg=MUTE, font=(F, 9)).pack(side="left")
        cb = ttk.Combobox(top, textvariable=dtv, values=DTYPES, state="disabled" if lock_type else "readonly", width=56); cb.pack(side="left", padx=8)
        mf = tk.Frame(win, bg=CARD); tk.Label(mf, text="Procurement mode:", bg=CARD, fg=MUTE, font=(F, 9)).pack(side="left")
        mcb = ttk.Combobox(mf, textvariable=pmv, values=PMODES, state="readonly", width=44); mcb.pack(side="left", padx=8)
        body = tk.Frame(win, bg=CARD); body.pack(padx=18, pady=4)
        def render(*a):
            keep = set(have) | {n for n, v in vs.items() if v.get()}
            for w_ in body.winfo_children(): w_.destroy()
            vs.clear(); d = dtv.get(); pmode = pmv.get() if d in MODE_TYPES else ""; need = set(req_docs(amt, d, pmode)); r = [0]
            if d in MODE_TYPES: mf.pack(fill="x", padx=18, pady=(8, 0), after=top)
            else: mf.pack_forget()
            def section(t, names):
                if not names: return
                tk.Label(body, text=t, bg=CARD, fg=NAVY, font=(F, 10, "bold")).grid(row=r[0], column=0, columnspan=2, sticky="w", pady=(10, 2)); r[0] += 1
                for i, n in enumerate(names):
                    v = tk.BooleanVar(value=n in keep); vs[n] = v
                    tk.Checkbutton(body, text=n + ("  *" if n in need else ""), variable=v, bg=CARD, activebackground=CARD, font=(F, 9), fg=INK, anchor="w", justify="left", wraplength=400).grid(row=r[0] + i // 2, column=i % 2, sticky="w", padx=6)
                r[0] += (len(names) + 1) // 2
            if d in CHECKLISTS:
                items = CHECKLISTS[d]
                section("Mandatory requirements (every DV)", MANDATORY); section(d, [n for n, ru in items if ru in ("R", "O")])
                section("Additional for purchases / services of ₱2,000 & above", [n for n, ru in items if ru == "2K"])
                if pmode in (PM_SVP, PM_SVPA): section("Additional for Small Value Procurement (new template)", [n for n, ru in items if ru == "SVP"])
                if pmode == PM_SVPA: section("Additional for Small Value Procurement above ₱200,000", [n for n, ru in items if ru == "SVPA"])
            elif d: section("Documents (old generic checklist)", LEGACY_DOCS)
            center(win)
        cb.bind("<<ComboboxSelected>>", render); mcb.bind("<<ComboboxSelected>>", render); render()
        tk.Label(win, text="*  = required for this DV      Unstarred items are optional or only if applicable.", bg=CARD, fg=MUTE, font=(F, 9)).pack(anchor="w", padx=18)
        def save():
            if not dtv.get(): return messagebox.showinfo("Choose a type", "Select the transaction type first.", parent=win)
            on_save(dtv.get(), {n for n, v in vs.items() if v.get()}, pmv.get() if dtv.get() in MODE_TYPES else ""); win.destroy()
        button(win, "Save", save).pack(pady=14)
        center(win); win.deiconify(); win.update()
        try: win.grab_set()
        except tk.TclError: pass
    def ask_text(self, title, prompt, initial=""):
        win = tk.Toplevel(self); win.withdraw(); win.title(title); win.configure(bg=CARD); win.transient(self); win.resizable(False, False); out = [None]
        tk.Label(win, text=prompt, bg=CARD, fg=INK, font=(F, 10), justify="left").pack(padx=26, pady=(22, 8), anchor="w")
        v = tk.StringVar(value=initial); ent = ttk.Entry(win, textvariable=v, width=38); ent.pack(padx=26, pady=4)
        def ok(*a): out[0] = v.get(); win.destroy()
        row = tk.Frame(win, bg=CARD); row.pack(pady=18); button(row, "OK", ok).pack(side="left", padx=6); button(row, "Cancel", win.destroy, "navy").pack(side="left", padx=6)
        win.bind("<Return>", ok); win.bind("<Escape>", lambda e: win.destroy())
        center(win); win.deiconify(); win.update()
        try: win.grab_set()
        except tk.TclError: pass
        ent.focus_set(); ent.selection_range(0, "end"); self.wait_window(win); return out[0]
    def edit_docs(self):
        ids = self.sel_ids()
        if len(ids) != 1: return messagebox.showinfo("Select one", "Select a single expense to update its documents.")
        i = ids[0]; lr, docs, amt, dv, dt, cat, pm = q("SELECT lr_no,docs,amount,dv_no,doc_type,category,proc_mode FROM expenses WHERE id=?", i)[0]
        if lr: return messagebox.showinfo("Locked", "Already liquidated. The School Head can undo the liquidation first.")
        def save(new_dt, ticked, new_pm): db.execute("UPDATE expenses SET docs=?, doc_type=?, proc_mode=? WHERE id=?", ("|".join(n for n in all_docs(new_dt) if n in ticked), new_dt, new_pm, i)); db.commit(); self.refresh()
        self.docs_dialog(f"Documents · DV {dv}", dt or SUGGEST.get(cat, ""), amt, set(docs.split("|")) if docs else set(), save, pm=pm)
    def undo_liq(self):
        ids = [i for i in self.sel_ids() if q("SELECT lr_no FROM expenses WHERE id=?", i)[0][0]]
        if not ids: return messagebox.showinfo("Select DVs", "Select one or more liquidated expenses first.")
        if messagebox.askyesno("Undo liquidation", f"Move {len(ids)} DV(s) back to unliquidated?"): db.executemany("UPDATE expenses SET lr_no='' WHERE id=?", [(i,) for i in ids]); db.commit(); self.refresh()
    def del_exp(self):
        s = self.et.selection()
        if not s: return
        i = self.et.item(s[0])["values"][0]
        if q("SELECT lr_no FROM expenses WHERE id=?", i)[0][0]: return messagebox.showerror("Blocked", "Already liquidated; cannot delete.")
        db.execute("DELETE FROM expenses WHERE id=?", (i,)); db.commit(); self.refresh()
    def r_exp(self):
        self.et.delete(*self.et.get_children())
        for r in q("SELECT e.id,f.name,e.dv_no,e.date,e.payee,e.category,e.amount,e.docs,e.lr_no,e.tax1+e.tax2,e.doc_type,e.proc_mode FROM expenses e JOIN funds f ON f.id=e.fund_id ORDER BY e.id DESC"):
            need = req_docs(r[6], r[10], r[11]); n = sum(d in r[7].split("|") for d in need)
            self.et.insert("", "end", tags=("ok" if r[8] else "warn" if n < len(need) else "",), values=(*r[:6], CODE.get(r[5], ""), money(r[6]), money(r[9]) if r[9] else "—", money(r[6] - r[9]), f"{n}/{len(need)}", r[8]))

    # ----- Liquidation report -----
    def p_lr(self, p):
        c = inner(card(p, "Prepare Liquidation Report")); c.master.pack(fill="x"); self.lrv = tk.StringVar()
        self.lr_cb = field(c, 0, 0, "Fund", self.lrv, [], True, 34); self.lr_cb.bind("<<ComboboxSelected>>", lambda e: self.r_lr())
        tk.Label(c, text="Only DVs with every required supporting document (DepEd MOOE checklist) are included; the rest are held back.", bg=CARD, fg=MUTE, font=(F, 9)).grid(row=1, column=1, sticky="w", padx=14)
        bt = tk.Frame(c, bg=CARD); bt.grid(row=3, column=0, columnspan=3, sticky="w", padx=14, pady=12)
        button(bt, "🖨  Printable report (HTML/PDF)", lambda: self.make_lr("html")).pack(side="left"); button(bt, "⬇  CSV export", lambda: self.make_lr("csv"), "navy").pack(side="left", padx=10)
        cp = inner(card(p, "Print liquidated transactions (already submitted — nothing is changed)")); cp.master.pack(fill="x", pady=(14, 0))
        self.plf, self.plr, self.pld1, self.pld2 = tk.StringVar(value=ALL), tk.StringVar(value="All LR numbers"), tk.StringVar(), tk.StringVar()
        self.plf_cb = field(cp, 0, 0, "Fund", self.plf, [ALL], True, 34); self.plr_cb = field(cp, 0, 1, "LR number", self.plr, ["All LR numbers"], True, 26)
        field(cp, 0, 2, "From date (optional)", self.pld1, None, False, 12); field(cp, 0, 3, "To date (optional)", self.pld2, None, False, 12)
        self.plf_cb.bind("<<ComboboxSelected>>", lambda e: self.r_print())
        bp = tk.Frame(cp, bg=CARD); bp.grid(row=3, column=0, columnspan=4, sticky="w", padx=14, pady=10)
        button(bp, "🖨  Print liquidated (HTML/PDF)", lambda: self.print_liq("html")).pack(side="left"); button(bp, "⬇  CSV", lambda: self.print_liq("csv"), "navy").pack(side="left", padx=10)
        c2 = card(p, "Ready vs. held back, by category"); c2.pack(fill="both", expand=True, pady=(14, 6))
        f, self.lt = table(c2, ("Category", "Ready to liquidate", "Held (incomplete docs)", "% of fund received"), {"Category": 280, "Ready to liquidate": 180, "Held (incomplete docs)": 200}, 6); f.pack(fill="both", expand=True, padx=12, pady=12)
        c3 = card(p, "Held back — missing required documents"); c3.pack(fill="both", expand=True, pady=(0, 6))
        f3, self.lh = table(c3, ("DV", "Transaction type", "Missing required documents"), {"DV": 70, "Transaction type": 260, "Missing required documents": 620}, 5); f3.pack(fill="both", expand=True, padx=12, pady=(2, 12))
    def items(self, fid):
        out = []
        for r in q("SELECT id,dv_no,date,payee,particulars,category,amount,doc_ref,docs,tax_type,tax1,tax2,doc_type,proc_mode FROM expenses WHERE fund_id=? AND lr_no=''", fid):
            out.append((r, all(d in r[8].split("|") for d in req_docs(r[6], r[12], r[13]))))
        return out
    def r_lr(self):
        self.lt.delete(*self.lt.get_children()); self.lh.delete(*self.lh.get_children())
        if not self.lrv.get(): return
        fid = self.fid(self.lrv.get()); rec = self.stats(fid)[0]; agg = {}
        for r, ok in self.items(fid):
            agg.setdefault(r[5], [0, 0])[0 if ok else 1] += r[6] - r[10] - r[11]
            if r[10] + r[11]: agg.setdefault("Due to BIR", [0, 0])[0 if ok else 1] += r[10] + r[11]
        for r, ok in self.items(fid):
            if not ok: self.lh.insert("", "end", values=(r[1], r[12] or "(old generic checklist)", "; ".join(d for d in req_docs(r[6], r[12], r[13]) if d not in r[8].split("|"))))
        for k, (a, b) in sorted(agg.items()): self.lt.insert("", "end", tags=("warn",) if b else (), values=(k, money(a), money(b), f"{(a + b) / rec * 100 if rec else 0:.1f}%"))
    def write_report(self, kind, path, title, fname, src, ref, lr, its, extra=()):
        """Write a CSV or printable-HTML report for the expense rows in `its` (same tuples as items()). Does not change any data."""
        tx1, tx2, gross = sum(r[10] for r in its), sum(r[11] for r in its), sum(r[6] for r in its); tot = {}
        for r in its: tot[r[5]] = tot.get(r[5], 0) + r[6] - r[10] - r[11]
        if tx1 + tx2: tot["Due to BIR"] = tot.get("Due to BIR", 0) + tx1 + tx2
        xh = [h for h, _ in extra]
        if kind == "csv":
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh); w.writerow([title]); w.writerow(["School", setting("school"), "Fund", fname, "LR No.", lr, "Printed", str(date.today())])
                w.writerow([]); w.writerow(["DV No.", "Date", "Payee", "Particulars", "Category", "Transaction Amount", "Less: Tax Withheld", "Net Expense", "OR/Invoice"] + xh)
                for r in its: w.writerow([r[1], r[2], r[3], r[4], f"{CODE.get(r[5], '')} {r[5]}".strip(), r[6], r[10] + r[11], r[6] - r[10] - r[11], r[7]] + [f(r) for _, f in extra])
                w.writerow([]); [w.writerow([k, v]) for k, v in tot.items()]; w.writerow(["TOTAL", sum(tot.values())]); w.writerow(["Income tax withheld", tx1]); w.writerow(["VAT / percentage tax withheld", tx2]); w.writerow(["Total tax to remit to BIR (Due to BIR 20201010-00)", tx1 + tx2]); w.writerow(["Net paid to payees", gross - tx1 - tx2])
            return
        e = lambda x: html.escape("" if x is None else str(x)); lg = logo_b64(); logo_tag = f'<p class=c><img src="{lg}" height=70></p>' if lg else ""
        rows = "".join(f"<tr><td>{e(r[1])}</td><td>{r[2]}</td><td>{e(r[3])}</td><td>{e(r[4])}</td><td>{e(r[5])}<br><small>{CODE.get(r[5], '')}</small></td><td class=n>{money(r[6])}</td><td class=n>{money(r[10] + r[11])}</td><td class=n>{money(r[6] - r[10] - r[11])}</td><td>{e(r[7])}</td>" + "".join(f"<td>{e(str(f(r)))}</td>" for _, f in extra) + "</tr>" for r in its)
        summ = "".join(f"<tr><td>{e(k)} <small>({CODE.get(k, '')})</small></td><td class=n>{money(v)}</td></tr>" for k, v in tot.items())
        head = "".join(f"<th>{h}</th>" for h in ["DV No.", "Date", "Payee", "Particulars", "Category", "Transaction Amount", "Less: Tax Withheld", "Net Expense", "OR/Invoice"] + xh)
        open(path, "w", encoding="utf-8").write(f"""<!doctype html><meta charset=utf-8><title>{e(lr)}</title><style>
body{{font:13px 'Segoe UI',Arial;color:#1B2A41;margin:36px}}h1{{font-size:17px;text-align:center;margin:2px}}.c{{text-align:center;color:#555}}
table{{border-collapse:collapse;width:100%;margin:14px 0}}th{{background:#0B1F3A;color:#fff;text-align:left}}th,td{{border:1px solid #bbb;padding:6px 8px}}.n{{text-align:right}}
.sig{{display:flex;justify-content:space-between;margin-top:60px}}.sig div{{width:40%;text-align:center;border-top:1px solid #000;padding-top:4px}}
.bar{{height:4px;background:#C9A227;margin:10px 0}}@media print{{button{{display:none}}}}</style>
<button onclick=print()>Print / Save as PDF</button>{logo_tag}<p class=c>Republic of the Philippines · Department of Education</p><h1>{e(setting('school') or 'SCHOOL NAME')}</h1>
<h1>{e(title)}</h1><div class=bar></div>
<p><b>Fund:</b> {e(fname)} {('(' + e(src) + ')') if src else ''} &nbsp; <b>Ref:</b> {e(ref or '-')} &nbsp; <b>LR No.:</b> {e(lr)} &nbsp; <b>Date printed:</b> {date.today():%B %d, %Y}</p>
<table><tr>{head}</tr>{rows}
<tr><td colspan=5><b>TOTAL</b></td><td class=n><b>{money(gross)}</b></td><td class=n><b>{money(tx1 + tx2)}</b></td><td class=n><b>{money(gross - tx1 - tx2)}</b></td><td colspan={1 + len(extra)}></td></tr></table>
<p><b>Transaction total:</b> ₱{money(gross)} &nbsp; <b>Less income tax withheld:</b> ₱{money(tx1)} &nbsp; <b>Less VAT / percentage tax withheld:</b> ₱{money(tx2)} &nbsp; <b>Total tax (Due to BIR 20201010-00):</b> ₱{money(tx1 + tx2)} &nbsp; <b>Net expense / paid to payees:</b> ₱{money(gross - tx1 - tx2)}</p>
<h3>Summary by account (net of tax; Due to BIR shown separately)</h3><table style=width:60%><tr><th>Account</th><th>Amount</th></tr>{summ}<tr><td><b>TOTAL (equals transaction total)</b></td><td class=n><b>{money(sum(tot.values()))}</b></td></tr></table>
<div class=sig><div>Prepared by: {e(self.user[0])}<br>Bookkeeper / Designated Officer</div><div>Certified correct:<br>School Head</div></div>""")
        webbrowser.open("file://" + path)
    def make_lr(self, kind):
        if not self.lrv.get(): return
        fid = self.fid(self.lrv.get()); its = [r for r, ok in self.items(fid) if ok]
        if not its: return messagebox.showinfo("Nothing to liquidate", "No expenses with complete required documents.")
        fname, src, ref = q("SELECT name,source,ref_no FROM funds WHERE id=?", fid)[0]; lr = f"LR-{date.today():%Y%m%d}-{fid}"
        path = filedialog.asksaveasfilename(defaultextension="." + kind, initialfile=lr + "." + kind)
        if not path: return
        self.write_report(kind, path, "REPORT ON SCHOOL MOOE AND OTHER FUNDS LIQUIDATION", fname, src, ref, lr, its)
        db.executemany("UPDATE expenses SET lr_no=? WHERE id=?", [(lr, r[0]) for r in its]); db.commit()
        messagebox.showinfo("Done", f"{len(its)} DV(s) marked liquidated under {lr}.\nAttach original supporting documents when submitting to the SDO."); self.refresh()

    # ----- Print already-liquidated transactions (read-only; never changes data) -----
    def liq_rows(self, where="", args=()):
        return q("SELECT e.id,e.dv_no,e.date,e.payee,e.particulars,e.category,e.amount,e.doc_ref,e.docs,e.tax_type,e.tax1,e.tax2,e.doc_type,e.proc_mode,e.lr_no,f.name FROM expenses e JOIN funds f ON f.id=e.fund_id "
                 "WHERE e.lr_no<>'' " + where + " ORDER BY e.lr_no,e.date,e.id", *args)
    def print_rows(self, kind, rows, fname, lr, multi_fund):
        if not rows: return messagebox.showinfo("Nothing to print", "No liquidated transactions match your selection.")
        extra = [("LR No.", lambda r: r[14])] + ([("Fund", lambda r: r[15])] if multi_fund else [])
        src = ref = ""
        if not multi_fund:
            fr = q("SELECT source,ref_no FROM funds WHERE name=?", rows[0][15]); src, ref = fr[0] if fr else ("", "")
        path = filedialog.asksaveasfilename(defaultextension="." + kind, initialfile=f"Liquidated-{date.today():%Y%m%d}." + kind)
        if path: self.write_report(kind, path, "LIQUIDATED TRANSACTIONS — REPORT ON SCHOOL MOOE AND OTHER FUNDS LIQUIDATION", fname, src, ref, lr, rows, extra)
    def print_liq(self, kind):
        w, a = "", []; f = self.plf.get()
        if f and f != ALL: w += " AND e.fund_id=?"; a.append(self.fid(f))
        lr = self.plr.get()
        if lr and lr != "All LR numbers": w += " AND e.lr_no=?"; a.append(lr)
        d1, d2 = self.pld1.get().strip(), self.pld2.get().strip()
        for d in (d1, d2):
            if d and not pdate(d): return messagebox.showerror("Check input", "Dates must be in YYYY-MM-DD format (or leave blank).")
        if d1: w += " AND e.date>=?"; a.append(d1)
        if d2: w += " AND e.date<=?"; a.append(d2)
        rows = self.liq_rows(w, a); multi = len({r[15] for r in rows}) > 1
        self.print_rows(kind, rows, "All funds" if multi or not rows else rows[0][15], lr if lr != "All LR numbers" else ", ".join(dict.fromkeys(r[14] for r in rows)) or "—", multi)
    def print_selected(self):
        ids = self.sel_ids(); rows = self.liq_rows(f" AND e.id IN ({','.join('?' * len(ids))})", ids) if ids else []
        if not rows: return messagebox.showinfo("Select liquidated DVs", "Select one or more liquidated expenses (rows with an LR No.) first.")
        multi = len({r[15] for r in rows}) > 1
        self.print_rows("html", rows, "All funds" if multi else rows[0][15], ", ".join(dict.fromkeys(r[14] for r in rows)), multi)
    def r_print(self):
        f = self.plf.get(); a = []; w = ""
        if f and f != ALL: w = " AND fund_id=?"; a.append(self.fid(f))
        lrs = [r[0] for r in q(f"SELECT DISTINCT lr_no FROM expenses WHERE lr_no<>'' {w} ORDER BY lr_no DESC", *a)]
        self.plr_cb["values"] = ["All LR numbers"] + lrs
        if self.plr.get() not in self.plr_cb["values"]: self.plr.set("All LR numbers")

    # ----- Settings (School Head) -----
    def p_set(self, p):
        c = inner(card(p, "School profile & deadline")); c.master.pack(fill="x"); self.sv = {"school": tk.StringVar(value=setting("school")), "days": tk.StringVar(value=setting("lr_days", "15"))}
        field(c, 0, 0, "School name (printed on reports)", self.sv["school"], w=40); field(c, 0, 1, "LR deadline: days after month-end (per SDO memo)", self.sv["days"], w=10)
        bt = tk.Frame(c, bg=CARD); bt.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=12); button(bt, "Save", self.save_set).pack(side="left"); button(bt, "⬇  Back up data", self.backup, "navy").pack(side="left", padx=10)
        row = tk.Frame(p, bg=BG); row.pack(fill="both", expand=True, pady=14); row.columnconfigure((0, 1), weight=1, uniform="s")
        o2 = card(row, "Spending caps per account (% of each quarterly release)"); o2.grid(row=0, column=0, sticky="nsew", padx=(0, 6)); g2 = tk.Frame(o2, bg=CARD); g2.pack(fill="x")
        self.cp = {"cat": tk.StringVar(), "pct": tk.StringVar()}; self.cp["cat"].set(LABELS[0])
        field(g2, 0, 0, "Account", self.cp["cat"], LABELS, True, 34); field(g2, 0, 1, "Cap % (0 removes)", self.cp["pct"], w=8)
        button(g2, "Set cap", self.set_cap).grid(row=2, column=0, sticky="w", padx=14, pady=10)
        f2, self.cpt = table(o2, ("Account", "Cap"), {"Account": 330, "Cap": 70}, 8); f2.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        c3 = inner(card(row, "User accounts")); c3.master.grid(row=0, column=1, sticky="nsew", padx=(6, 0)); self.nu = {k: tk.StringVar() for k in "upr"}; self.nu["r"].set(ROLES[1])
        field(c3, 0, 0, "Username", self.nu["u"]); field(c3, 1, 0, "Password (min. 6)", self.nu["p"]); field(c3, 2, 0, "Role", self.nu["r"], ROLES, True)
        button(c3, "＋  Add user", self.add_user).grid(row=6, column=0, sticky="w", padx=14, pady=12)
        self.ul = tk.Listbox(c3, height=6, relief="flat", font=(F, 10), bg=CARD, highlightthickness=0); self.ul.grid(row=7, column=0, padx=14, sticky="ew")
    def backup(self):
        p = filedialog.asksaveasfilename(defaultextension=".db", initialfile=f"liquidation-backup-{date.today()}.db")
        if p: b = sqlite3.connect(p); db.backup(b); b.close(); messagebox.showinfo("Backup saved", f"Copy this file somewhere safe (USB drive or cloud):\n{p}\n\nLive data folder:\n{DATA}")
    def save_set(self): put("school", self.sv["school"].get().strip()); put("lr_days", str(int(num(self.sv["days"].get()) or 15))); messagebox.showinfo("Saved", "Settings saved.")
    def set_cap(self):
        name, pct = self.cp["cat"].get().split(" · ", 1)[-1], num(self.cp["pct"].get())
        if pct <= 0: db.execute("DELETE FROM caps WHERE category=?", (name,))
        else: db.execute("INSERT OR REPLACE INTO caps VALUES(?,?)", (name, min(pct, 100)))
        db.commit(); self.cp["pct"].set(""); self.refresh()
    def add_user(self):
        u, pw = self.nu["u"].get().strip(), self.nu["p"].get()
        if not u or len(pw) < 6: return messagebox.showerror("Check input", "Username required; password min. 6 characters.")
        if q("SELECT 1 FROM users WHERE username=?", u): return messagebox.showerror("Exists", "Username already taken.")
        s = secrets.token_hex(16); db.execute("INSERT INTO users VALUES(?,?,?,?)", (u, s, hpw(pw, s), self.nu["r"].get())); db.commit(); self.nu["u"].set(""); self.nu["p"].set(""); self.refresh()

    def sources(self):
        return SOURCES + sorted({r[0] for r in q("SELECT source FROM funds UNION SELECT source FROM allocations") if r[0] and r[0] not in SOURCES})
    def refresh(self):
        src = self.sources(); self.src_cb1["values"] = self.src_cb2["values"] = src; self.dcb["values"] = [ALL] + src; self.dycb["values"] = ["All years"] + [str(r[0]) for r in q("SELECT DISTINCT fy FROM funds WHERE fy IS NOT NULL ORDER BY fy DESC")]
        names = self.fund_names()
        for cb in (self.fund_cb, self.lr_cb): cb["values"] = names
        self.plf_cb["values"] = [ALL] + names
        for v in (self.ev["fund"], self.lrv):
            if names and v.get() not in names: v.set(names[0])
        self.r_funds()
        self.r_dash(); self.r_exp(); self.r_lr(); self.r_print()
        if "Settings" in self.pages: self.ul.delete(0, "end"); [self.ul.insert("end", f"{u}  ·  {r}") for u, r in q("SELECT username,role FROM users")]; self.cpt.delete(*self.cpt.get_children()); [self.cpt.insert("", "end", values=(f"{CODE.get(k, '')} · {k}", f"{v:g}%")) for k, v in q("SELECT category,pct FROM caps WHERE pct>0 ORDER BY category")]

if __name__ == "__main__":
    import traceback
    try: App().mainloop()
    except Exception:
        err = traceback.format_exc(); open(os.path.join(DATA, "error.log"), "w").write(err)
        r = tk.Tk(); r.withdraw(); messagebox.showerror("Startup error", err[-1500:]); r.destroy()
