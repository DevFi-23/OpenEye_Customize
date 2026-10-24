"""show_spad.py <dump.json> [pe ...]: final weight address / data SPad contents per PE (first load only)."""
import json, sys

def s8(v):
    return v - 256 if v >= 128 else v

def load(path):
    log = json.load(open(path))
    out = {}
    for pe, ev in log.items():
        addr, data, order = {}, {}, []
        for e in ev:
            if e[0] == "A":
                addr[e[2]] = e[3]
                order.append(("A", e[2], e[3]))
            elif e[0] == "D":
                data[e[2]] = e[3]
                order.append(("D", e[2], e[3]))
        if addr or data:
            out[pe] = (addr, data, order)
    return out

def entries(word):
    lo, hi = word & 0xFFF, word >> 12
    return [(s8(lo & 0xFF), lo >> 8), (s8(hi & 0xFF), hi >> 8)]

if __name__ == "__main__":
    spads = load(sys.argv[1])
    pes = sys.argv[2:] or sorted(spads)[:3]
    print("PEs with weight writes:", len(spads), sorted(spads))
    for pe in pes:
        addr, data, order = spads[pe]
        print(f"== PE {pe}: addr SPad {[addr[a] for a in sorted(addr)]} (addresses {sorted(addr)})")
        print("   data SPad:", [(a, entries(data[a])) for a in sorted(data)])
        print("   write order:", order[:80])
