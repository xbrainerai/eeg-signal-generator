# fix_raw_packets.py
with open("raw_packets.jsonl", "r", encoding="latin1") as f:
    raw = f.read()

# Insert newline between JSON objects if missing
fixed = raw.replace('}{', '}\n{')

with open("fixed_packets.jsonl", "w", encoding="utf-8") as f:
    f.write(fixed)
