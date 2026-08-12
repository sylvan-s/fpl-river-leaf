import build_squad as bs
import statistics

pool_on = bs.load(bonus=True)
pool_off = bs.load(bonus=False)
off_map = {(r['name'], r['team']): r['score'] for r in pool_off}
rows = []
for r in pool_on:
    key = (r['name'], r['team'])
    off = off_map.get(key)
    if off is None:
        continue
    rows.append((r['name'], r['team'], r['pos'], r['price'], off, r['score'],
                 r['score'] - off, r.get('xbonus90', 0.0)))
rows.sort(key=lambda x: -x[6])

hdr = "name           team pos  price   xP off  xP on   swing   xbonus90"
print(hdr)
for row in rows[:15]:
    print(f"{row[0]:14s} {row[1]:4s} {row[2]:4s} £{row[3]:<5.1f} {row[4]:<7.2f} {row[5]:<7.2f} {row[6]:<+7.2f} {row[7]:<7.2f}")
print("...")
for row in rows[-8:]:
    print(f"{row[0]:14s} {row[1]:4s} {row[2]:4s} £{row[3]:<5.1f} {row[4]:<7.2f} {row[5]:<7.2f} {row[6]:<+7.2f} {row[7]:<7.2f}")

swings = [r[6] for r in rows]
print()
print("mean swing", round(statistics.mean(swings), 3),
      "mean |swing|", round(statistics.mean(abs(s) for s in swings), 3),
      "max", round(max(swings), 3), "min", round(min(swings), 3))

print()
print("--- specific comparisons ---")
lookup = {(r[0]): r for r in rows}
for n in ("Rice", "Sarr", "Gabriel", "B.Fernandes", "Mbeumo", "Palmer", "Van den Berg", "Mosquera"):
    if n in lookup:
        r = lookup[n]
        print(f"{r[0]:14s} xP off={r[4]:.2f}  xP on={r[5]:.2f}  swing={r[6]:+.2f}  xbonus90={r[7]:.2f}")
