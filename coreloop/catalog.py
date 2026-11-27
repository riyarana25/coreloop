"""Invented catalog and OEM policy table. NOT real OEM rules or prices."""
from .models import OEMPolicy, Part

POLICIES = {
    "OEM-A": OEMPolicy("OEM-A", window_days=21, transit_days=3, posting_days=14, grace_days=3,
                       max_damage_deduction=0.30, dispute_window_days=60, freight_cost=45.0),
    "OEM-B": OEMPolicy("OEM-B", window_days=30, transit_days=4, posting_days=21, grace_days=5,
                       max_damage_deduction=0.25, dispute_window_days=45, freight_cost=55.0),
    "OEM-C": OEMPolicy("OEM-C", window_days=14, transit_days=2, posting_days=10, grace_days=3,
                       max_damage_deduction=0.30, dispute_window_days=30, freight_cost=40.0),
}

_PARTS = [
    # part_no, oem, core_value, supersedes
    ("A-1100", "OEM-A", 85.0, None),    # alternator
    ("A-1204", "OEM-A", 140.0, None),   # starter
    ("A-2310", "OEM-A", 620.0, "A-2301"),  # transmission control module (renumbered)
    ("A-2301", "OEM-A", 410.0, None),
    ("A-3050", "OEM-A", 60.0, None),    # brake caliper
    ("B-4400", "OEM-B", 260.0, None),   # AC compressor
    ("B-4512", "OEM-B", 900.0, "B-4507"),  # high-voltage unit (renumbered)
    ("B-4507", "OEM-B", 520.0, None),
    ("B-5120", "OEM-B", 75.0, None),
    ("B-5230", "OEM-B", 190.0, None),   # power steering rack
    ("C-6001", "OEM-C", 340.0, None),   # turbocharger
    ("C-6110", "OEM-C", 120.0, None),
    ("C-6225", "OEM-C", 760.0, "C-6218"),  # ECU (renumbered)
    ("C-6218", "OEM-C", 480.0, None),
]

PARTS = {p[0]: Part(*p) for p in _PARTS}

# Parts that are currently sold/installed (not just old numbers kept for credit lookups).
_SUPERSEDED = {p.supersedes for p in PARTS.values() if p.supersedes}
ACTIVE_PARTS = sorted(pn for pn in PARTS if pn not in _SUPERSEDED)
