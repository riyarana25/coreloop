"""A transparent freight cost model for core returns. ALL VALUES ARE ILLUSTRATIVE ASSUMPTIONS.

Cost of one shipment = max(minimum charge, base fee + linehaul) + packaging per core
    linehaul = rate_per_cwt_mile x miles x (weight / 100), with a discount above a weight break
A load heavier than the capacity is split into several shipments (each pays its own base fee).
Shipment count alone is NOT freight cost: heavier consolidated loads still pay for weight and distance.
"""
from dataclasses import dataclass, field

# invented weights (lb) for the 14 invented parts
CORE_WEIGHT_LB = {"A-1100": 12, "A-1204": 8, "A-2310": 3, "A-2301": 3, "A-3050": 10, "B-4400": 15,
                  "B-4512": 40, "B-4507": 38, "B-5120": 6, "B-5230": 25, "C-6001": 12, "C-6110": 7,
                  "C-6225": 2, "C-6218": 2}


@dataclass(frozen=True)
class FreightParams:
    distance_miles: dict = field(default_factory=lambda: {"OEM-A": 350, "OEM-B": 900, "OEM-C": 150})
    base_fee: float = 28.0
    min_charge: float = 45.0
    rate_per_cwt_mile: float = 0.10          # $ per 100 lb per mile
    weight_break_lb: float = 200.0
    weight_break_discount: float = 0.20
    capacity_lb: float = 500.0
    packaging_per_core: float = 4.0


def split_loads(weights, capacity):
    """First-fit-decreasing split of core weights into loads no heavier than `capacity`."""
    loads = []
    for w in sorted(weights, reverse=True):
        for ld in loads:
            if sum(ld) + w <= capacity:
                ld.append(w)
                break
        else:
            loads.append([w])
    return loads


def shipment_cost(oem, weights, fp=FreightParams()):
    """Cost of shipping cores with these weights to `oem` on one day. Returns (cost, n_loads, total_lb)."""
    total, cost = sum(weights), 0.0
    loads = split_loads(weights, fp.capacity_lb)
    for ld in loads:
        w = sum(ld)
        rate = fp.rate_per_cwt_mile * (1 - fp.weight_break_discount if w > fp.weight_break_lb else 1.0)
        line = rate * fp.distance_miles[oem] * w / 100.0
        cost += max(fp.min_charge, fp.base_fee + line)
    return cost + fp.packaging_per_core * len(weights), len(loads), total


def plan_freight(schedule, cores_by_id, fp=FreightParams()):
    """schedule: {(oem, day): [core_id]} -> dict(freight, shipments(loads), cores, total_lb, utilisation)."""
    freight = loads = lb = 0.0
    n_cores = 0
    for (oem, _day), ids in schedule.items():
        ws = [CORE_WEIGHT_LB[cores_by_id[i].part_no] for i in ids]
        c, nl, tot = shipment_cost(oem, ws, fp)
        freight += c
        loads += nl
        lb += tot
        n_cores += len(ids)
    return {"freight": freight, "loads": loads, "cores": n_cores, "total_lb": lb,
            "utilisation": lb / (loads * fp.capacity_lb) if loads else 0.0}
