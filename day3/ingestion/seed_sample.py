#!/usr/bin/env python3
"""
Seed script — generates a synthetic bond prospectus PDF for ISIN XS1234567890
and ingests it into ChromaDB.

The call schedule in the PDF intentionally differs from the security master
value of "par flat" to demonstrate the mismatch-detection demo:

  Prospectus:       "par + 0.5% call premium from 15 January 2027"
  Security master:  "par flat"

Run from the repository root:
  python -m day3.ingestion.seed_sample
"""

import os
import sys
from pathlib import Path

# Allow running as a script from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from fpdf import FPDF  # fpdf2

ISIN = "XS1234567890"
OUTPUT_DIR = Path(__file__).parent / "sample_pdfs"
PDF_PATH = OUTPUT_DIR / f"{ISIN}_prospectus.pdf"

# ---------------------------------------------------------------------------
# Prospectus content
# ---------------------------------------------------------------------------

SECTIONS = [
    (
        "Bond Summary",
        f"""ISIN: {ISIN}
Issuer: Acme Corporation PLC
Issue Date: 15 January 2022
Maturity Date: 15 January 2032
Principal Amount: USD 500,000,000
Currency: US Dollar (USD)
Status: Senior Unsecured
Governing Law: English Law
Listing: London Stock Exchange (LSE), International Securities Market

This document constitutes the prospectus for the USD 500,000,000 Senior Unsecured
Fixed Rate Notes due 2032 issued by Acme Corporation PLC (the "Issuer").
The Notes are offered pursuant to this Prospectus dated 15 January 2022.""",
    ),
    (
        "Coupon Terms",
        """COUPON RATE: 4.500% per annum
Payment Frequency: Semi-annual
Coupon Payment Dates: 15 January and 15 July of each year, commencing 15 July 2022.
Day Count Convention: 30/360 (Bond Basis)
Business Day Convention: Following Business Day Convention
Business Days: London and New York

The Notes bear interest from and including the Issue Date at the rate of 4.500% per
annum on their outstanding principal amount. Interest shall accrue from day to day.
If any interest payment date falls on a day that is not a Business Day, the payment
shall be made on the next succeeding Business Day.""",
    ),
    (
        "Call Schedule",
        """ISSUER CALL OPTION

The Issuer may, at its option, redeem all (but not some only) of the Notes on any
Coupon Payment Date falling on or after 15 January 2027 (the "First Call Date")
at the following redemption prices:

  - On or after 15 January 2027: par + 0.5% call premium (100.500% of principal)
  - On or after 15 January 2028: par + 0.375% call premium (100.375% of principal)
  - On or after 15 January 2029: par + 0.25% call premium (100.250% of principal)
  - On or after 15 January 2030: par + 0.125% call premium (100.125% of principal)
  - On or after 15 January 2031: par (100.000% of principal)

The bond may be called at par + 0.5% premium on any coupon date from 15 January 2027.

Notice of redemption must be given by the Issuer to the Noteholders not less than
15 nor more than 30 days prior to the relevant redemption date. Such notice shall
be irrevocable and shall specify the redemption date.

Make-Whole Call: Prior to 15 January 2027, the Issuer may redeem all (but not some
only) of the Notes at a redemption price equal to the greater of (i) the principal
amount of the Notes and (ii) the sum of the present values of the remaining scheduled
payments of principal and interest, discounted at the Comparable Treasury Rate plus
50 basis points, plus in each case accrued and unpaid interest.""",
    ),
    (
        "Put Schedule",
        """NOTEHOLDER PUT OPTION

Each Noteholder has the right to require the Issuer to redeem all or some of that
Noteholder's Notes on the following dates at the specified prices:

  Put Date 1: 15 January 2027 — at par (100.000% of principal)
  Put Date 2: 15 January 2029 — at par (100.000% of principal)

To exercise the put option, a Noteholder must deliver a Put Exercise Notice to the
relevant Paying Agent not less than 30 nor more than 60 days prior to the relevant
Put Date. Such notice shall be irrevocable.

In the event of a Change of Control, Noteholders will have the right to require the
Issuer to redeem the Notes at 101.000% of principal plus accrued interest (the
"Change of Control Put").""",
    ),
    (
        "Redemption Terms",
        """REDEMPTION AT MATURITY

Unless previously redeemed or purchased and cancelled, the Issuer will redeem the
Notes at par (100.000% of their principal amount) on 15 January 2032 (the
"Maturity Date") together with accrued and unpaid interest.

TAXATION / GROSS-UP

All payments of principal and interest by the Issuer shall be made without
withholding or deduction for or on account of any present or future taxes unless
required by law. If any withholding or deduction is required, the Issuer shall pay
such additional amounts as may be necessary so that the net amount received equals
the amount that would have been received in the absence of such withholding.

TAX CALL

The Issuer may redeem all (but not some only) of the Notes at par plus accrued
interest if, as a result of any change in tax law, the Issuer would be required to
pay additional amounts in respect of the Notes on the next Interest Payment Date.""",
    ),
    (
        "Covenants",
        """NEGATIVE PLEDGE

The Issuer will not, and will procure that none of its Principal Subsidiaries will,
create or permit to subsist any Security over all or any part of its present or
future assets or revenues to secure any Relevant Indebtedness unless the Notes are
simultaneously secured equally and ratably with such Relevant Indebtedness.

CROSS-DEFAULT

An Event of Default will occur if (a) any Indebtedness of the Issuer or any
Principal Subsidiary becomes due and repayable prematurely by reason of an event of
default (however described) or (b) any such Indebtedness is not paid when due or,
as the case may be, within any applicable grace period, provided that the aggregate
amount of all Indebtedness in respect of which one or more of the events mentioned
above have occurred equals or exceeds USD 50,000,000 (or its equivalent).

REPORTING

The Issuer shall provide to the Trustee within 180 days after each financial year
end audited consolidated financial statements and within 90 days after each
half-year end unaudited consolidated interim financial statements.""",
    ),
]


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


def create_prospectus_pdf(output_path: Path) -> Path:
    """Generate a synthetic bond prospectus PDF and save to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title page
    pdf.set_font("Helvetica", "B", size=20)
    pdf.cell(0, 15, "OFFERING CIRCULAR", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", size=16)
    pdf.cell(0, 12, "Acme Corporation PLC", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", size=13)
    pdf.cell(
        0,
        10,
        "USD 500,000,000 4.500% Senior Unsecured Fixed Rate Notes due 2032",
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.ln(3)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"ISIN: {ISIN}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, "Issue Date: 15 January 2022", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", size=9)
    pdf.multi_cell(
        0,
        6,
        (
            "This Offering Circular has been prepared by Acme Corporation PLC solely for "
            "use in connection with the offering of the Notes described herein. This document "
            "is for information purposes only and does not constitute a prospectus for the "
            "purposes of the EU Prospectus Regulation."
        ),
        align="C",
    )

    # Sections
    for title, body in SECTIONS:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", size=14)
        pdf.cell(0, 10, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, body)

    pdf.output(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    from day3.ingestion.pdf_ingester import PDFIngester

    pdf_path = create_prospectus_pdf(PDF_PATH)
    print(f"Generated prospectus PDF: {pdf_path}")

    ingester = PDFIngester()
    n = ingester.ingest_sync(str(pdf_path), ISIN, document_type="prospectus", force=True)
    print(f"Seeded prospectus for {ISIN} — {n} chunks stored")


if __name__ == "__main__":
    main()
