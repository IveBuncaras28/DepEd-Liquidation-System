# DepEd School Liquidation Monitor

A desktop app for public schools to track funds received from the SDO, record disbursements,
monitor liquidation deadlines, and produce Liquidation Reports. Runs offline. Python 3.9+ only,
no packages to install.

## Install (Windows)
**Easiest (needs internet only the first time):** double-click `Install.bat`. It installs Python automatically if missing, puts the app in your user folder, and adds *DepEd Liquidation Monitor* to the Desktop and Start menu. `Uninstall.bat` removes the program but keeps your data.

**Single setup file for other computers:** on any Windows PC with Python, double-click `build_installer.bat`. It creates `dist\DepEdLiquidation.exe` (runs without Python) and, if Inno Setup 6 (free) is installed, `Output\DepEd_Liquidation_Setup.exe`, a normal setup wizard you can copy to a USB drive.

The app has its own icon (`app.ico`, a gold peso sign with a green check) on the shortcuts, window, taskbar and the built `.exe` / setup file. To use a different logo, replace `app.ico` and `app.png` before installing or building.

**DepEd logo:** the official seal is included as `deped_logo.png` and appears on the sign-in screen, the sidebar and the printed liquidation report. To use a different logo, replace that file (square PNG, 300 px or larger) before running `Install.bat` or `build_installer.bat`, or drop it into `%APPDATA%\\DepEdLiquidation` on an installed copy. `Install.bat` also installs the small free *Pillow* package so the logo is scaled smoothly (the app still works without it).

Your data is stored in `%APPDATA%\DepEdLiquidation\liquidation.db`, so it survives updates and reinstalls. Use **Settings > Back up data** regularly.

## Quick start
1. Install Python 3.9+ (Windows: python.org, tick "Add to PATH"; Tkinter is included).
2. Put `deped_liquidation.py` in a folder and run: `python deped_liquidation.py`
3. First launch: create the **School Head** account (password min. 6 characters).
4. **Settings** → enter the school name, the LR deadline days from your SDO memo, and optional category caps.

Data is saved in `%APPDATA%\DepEdLiquidation\liquidation.db` (on Windows). Use **Settings > Back up data** to save a copy.

## Daily workflow
1. **Funds Received** – the main fund types are **Regular MOOE Fund SHS** and **Regular MOOE Fund JHS**, and there are other sources too (GAD Fund, Canteen/Other School Fund, SEF/Program Fund, Other). Type a new source name in the box to add your own. Funds are released **quarterly**, so record each release as its own entry (fiscal year, Q1-Q4, fund type, ref no., amount, date). Every source is tracked, liquidated and reported separately, and the Dashboard can be filtered by fund source, fiscal year and quarter (Q1-Q4). Optionally enter the **annual allocation** from the SDO's written notice; the table then shows released so far, still to be released, and which quarters have arrived. The app warns if releases exceed the annual allocation or if a quarter is entered twice. The LR due date is computed automatically (month-end + deadline days) or typed manually.
2. **Expenses / DVs** – record every paid DV with account, amount, OR/invoice no. and **transaction type**. The type (Travel, Office/School Supplies & Photocopy, Repair/Rehab/Construction, Labor, Repairs of Office/ICT Equipment, Jobbers/Watchman/School Aide, Electricity/Water/Internet, Mobile Expenses, Food & Meals/Catering, Hauling, Sound System Rental/Other Materials with no OR, Fidelity Bond) loads the DepEd *MOOE List of Attachments* checklist (revised version); it is suggested automatically from the account. For supplies and repair/rehab/construction purchases, also pick the **Procurement mode**: *Direct Acquisition*, *Small Value Procurement below ₱200,000* (adds BAC Resolution-Employ, Canvass/RFQ, Opening of Canvass, Abstract of Bid as Read, BAC Resolution-Award) or *above ₱200,000* (also PhilGEPS posting, Notice of Award, Notice to Proceed). Press **Supporting documents…** and tick what you have.
3. **Dashboard** – watch balances, % used, overdue/due-soon reports, incomplete documents, and spending by category.
3a. **Printing liquidated transactions** – on **Liquidation Report > Print liquidated transactions**, choose a fund (or all funds), an LR number (or all) and an optional date range, then print (HTML/PDF) or export CSV. On **Expenses / DVs** you can also select liquidated rows and press **Print selected liquidated**. Printing never changes any data, so you can reprint any time.
3b. **Marking as liquidated** – on **Expenses / DVs**, select one or more rows (Ctrl+click or Shift+click for several) and press **Mark selected as liquidated**, then enter the LR number. Use this for reports you already submitted. Forgot to tick a document? Select the row and press **Update documents**. The School Head can **Undo liquidation** if it was a mistake.
4. **Liquidation Report** – pick the fund, then export a printable report (open in browser → Print/Save as PDF) or CSV. Exported DVs are marked liquidated and locked.

## Tax withholding (purchases and services of ₱2,000 and above)
Pick a tax type on the expense form and the app computes the withholding from the school's posted guide, using the gross amount:

| Type | First rate | Second rate |
|---|---|---|
| Goods - VAT | (Gross / 1.12) x 1% | (Gross / 1.12) x 5% |
| Services - VAT | (Gross / 1.12) x 2% | (Gross / 1.12) x 5% |
| Goods - Non-VAT | Gross x 1% | Gross x 3% |
| Services - Non-VAT | Gross x 2% | Gross x 3% |

The amount you enter is the **transaction amount**. The tax is **subtracted from it** (never added on top): net expense = transaction amount − tax withheld. The net expense is recorded under the chosen account (and counts toward its cap); the tax is recorded on its own line under **Due to BIR (20201010-00)**. The two lines add back to the transaction amount, which is what leaves the fund. Reports show transaction amount, less tax, and net expense for every DV. For purchases of ₱2,000 and above, "PO/docs received by COA" is also a required document before the DV can be liquidated (per the reminder on the school's guide).

## Built-in controls
- Disbursements cannot exceed the fund balance; duplicate DV numbers are rejected.
- Supporting documents follow the DepEd MOOE checklist: the mandatory items (CDR, SoA, Updated Check Ledger, APP, Market Scoping Form, PPMP, Check Disbursement Voucher, photocopy of check) for every DV, the list for the transaction type and procurement mode, and BIR Form 2307 plus "PO/docs received by COA" for purchases and services of ₱2,000 and above (tax rules unchanged). Only DVs with every required item (marked *) enter a report; the others are held back and the Liquidation Report page lists exactly what is missing.
- Each quarterly release is tracked separately (balance, liquidation and caps per release). An unspent balance from an earlier quarter stays in that release and can still be charged in the same fiscal year.
- Spending caps per account (percent of each quarterly release) warn (with confirmation) when exceeded.
- Roles: **School Head** (settings, users, delete funds) and **Bookkeeper** (day-to-day entry). Passwords are salted and hashed (PBKDF2).

## Legal basis (verify current versions)
DepEd Order 8 s.2019 (use, monitoring and reporting of school MOOE) · DepEd Order 29 s.2019 and COA-DBM-DepEd Joint Circular 2019-1 (cash advances of non-implementing units; SDO replenishes within 3 working days of receiving the LR) · Government Accounting Manual (COA Circular 2015-007).

## Customize (top of `deped_liquidation.py`)
`ACCOUNTS` (the school's MOOE chart of accounts with UACS codes), `SOURCES` and `DOCS` can be edited to match your SDO's checklists. The default 15-day
deadline is a placeholder; follow your SDO's memo.

## Limits
This is a monitoring and reporting aid, not the official accounting system. It does not generate the JEV or
Cash Disbursement Register some SDOs require, and there is no password recovery: keep a second School Head-level
login safe, or ask a technical person to reset the users table.

## Note on the revised MOOE checklist
Older DVs are carried over automatically (renamed items such as *Subsidiary Ledger* become *Updated Check Ledger*). Because the mandatory list now also includes APP, Market Scoping Form and PPMP, DVs that are not yet liquidated may show as missing those items until you tick them. Transaction types dropped from the revised list (Teacher's ID, Check Book, GAD) remain usable only for DVs already recorded under them.
