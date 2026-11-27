# Competitive analysis (public information only)

| Product (source) | Who it serves | Core tracking | Credit reconciliation | Deadline-aware shipping | Continuous monitoring | Gap CoreLoop targets |
|---|---|---|---|---|---|---|
| Tekmetric (S6) | Independent repair shops | Yes: core line items, return orders | Partly: "Refund Pending" list is the credit receivable; closed manually when a credit memo arrives | Not found | Not found | Nobody compares the credit to the expected amount or watches the clock |
| R.O. Writer (S7) | Shops | Yes: core returns screen, credit posting to AP | Credit posted by the user | Not found | Not found | Same |
| Auto/Mate DMS (S8) | Dealers | Yes: "automatic core tracking", pending credit value, superseded-parts tracking | Pending-credit visibility. Dispute workflow not found | Not found | Not found | Closest to CoreLoop; the differentiation is the temporal alerts and shipment planning, which I did not find described |
| AMT, Omnique, ShopView (S9, S21) | Shops | Yes, with statuses | Manual status changes | Pending/overdue reports | Reports, not alerts | Same |
| CCC credit memos (S10) | Collision shops | Credit memo records | Record keeping | Not found | Not found | Same |
| RLMS (S11) | OEMs, suppliers, dealers: **supplier-side** | Online return, barcodes, inspection, credit release | Supplier side issues the credit | Not found | Not found | Opposite side of the exchange; a possible data source, not a substitute |
| ReverseLogix (S12) | Manufacturers/distributors | Yes | Returns and warranty | Not found | Not found | Different buyer (manufacturer) |
| WickedFile (S13) | Repair shops | Reads vendor documents | Yes: matches vendor invoices/credit memos | Not found | Document-triggered | Overlaps on credit reconciliation. Does not appear to plan shipments |
| SPS Commerce (S14) | Suppliers | Return lifecycle framework | Reconciliation emphasised | n/a | n/a | Conceptual support that reconciliation is a known problem |

## Honest reading

- Core **tracking** and credit **posting** are crowded. CoreLoop must not be pitched as "we track cores".
- Credit **reconciliation against the entitled amount** exists in at least one product (WickedFile, by its own description), so it is not unique either.
- What I did not find described in public pages: (1) a calendar-aware planner that consolidates return shipments against OEM windows while holding a safety buffer, and (2) a classifier that separates "pending", "at risk" and "action required" using the learned posting delay of each OEM. That is a narrower claim than "nobody does this" and it is stated as "not found".
- Pitch positioning: not a new core tracker, but the **deadline layer** on top of one.
