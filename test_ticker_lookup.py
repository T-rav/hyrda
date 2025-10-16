#!/usr/bin/env python3
"""Quick test of expanded ticker lookup for mid-sized companies."""

import sys
from pathlib import Path

# Add tasks to path
sys.path.insert(0, str(Path(__file__).parent))

from tasks.services.sec_edgar_client import SECEdgarClient

# Test various company sizes
test_companies = [
    # Large cap
    ("AAPL", "Apple Inc"),
    ("MSFT", "Microsoft"),

    # Mid cap
    ("ZM", "Zoom Video"),
    ("DOCU", "DocuSign"),
    ("TWLO", "Twilio"),
    ("NET", "Cloudflare"),

    # Smaller cap
    ("FROG", "JFrog"),
    ("GTLB", "GitLab"),

    # Should fail
    ("NOTREAL", "Fake Company"),
]

print("Testing SEC Ticker Lookup (13,000+ companies)")
print("=" * 60)

for ticker, expected_name in test_companies:
    cik = SECEdgarClient.lookup_cik(ticker)
    status = "✅" if cik else "❌"
    result = cik if cik else "NOT FOUND"
    print(f"{status} {ticker:10} → {result:15} ({expected_name})")

print("=" * 60)
print("\nTest complete!")
