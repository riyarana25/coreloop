# Tekion product landscape and the seven questions

Method: public Tekion pages and the two developer-doc pages reviewed earlier (S1-S5). Status labels: **Confirmed**, **Partially confirmed**, **Not found in public documentation**, **Unknown**. "Not found" means I did not find it in public pages. It does not mean Tekion lacks it; DMS parts modules routinely have some core handling and Tekion's partner/customer portals are not public.

| # | Question | Status | Evidence and caveat |
|---|---|---|---|
| 1 | Does ARC track core charges / core deposits on parts sold? | **Not found in public documentation** | S1, S3 describe a parts department but not core deposits. S5 pages reviewed do not mention cores. Competing DMS/shop tools do (S6-S9), so absence here is more likely a documentation gap than a missing feature. Unknown |
| 2 | Does ARC reconcile OEM/vendor credit memos against the core deposit that was paid? | **Not found in public documentation** | No page found. Even in tools that track cores, the credit is typically marked complete by hand (S6) |
| 3 | Does ARC raise deadline alerts for OEM core-return windows? | **Not found in public documentation** | No page found |
| 4 | Does Tekion handle part-number supersession in some form? | **Partially confirmed** | S2: special-order parts tracking handles part-number changes and substitutes. Nothing says a returned core credited at a superseded number is detected |
| 5 | Can a third party integrate with Tekion data (parts, orders, accounting)? | **Confirmed** | S1: Automotive Partner Cloud, 390 APIs, 500+ registered partners, an App Store with dealer installs. Access is partner-gated; which APIs expose parts/returns data is **Unknown** |
| 6 | Does Tekion connect parts operations to OEMs? | **Partially confirmed** | S3 and S4 say parts stays connected to OEMs. No detail on core credit flows |
| 7 | Does Tekion publish a circular-parts or core-exchange marketplace? | **Not found in public documentation** | Nothing found. The hackathon's own theme wording is known to me only from the participant |

## What this means for CoreLoop

- CoreLoop is positioned as a layer that **sits on Tekion's data through APC**, not as a replacement for any Tekion module. That is a plan, not a verified integration. No Tekion integration is built or claimed.
- Whether Tekion already does questions 1-3 internally is the main risk to the pitch. The honest framing is: "We found no public evidence of continuous deadline-aware core monitoring; here is the evidence of value if it is absent, and a design that complements it if it is present."
