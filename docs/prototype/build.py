"""Build docs/prototype/radixark-gtm-os.html from the seed register.
Run: python3 docs/prototype/build.py
"""
import json, pathlib
root = pathlib.Path(__file__).resolve().parents[2]
seed = json.load(open(root / "data/seed/radixark-crm-seed.json"))
tpl = (root / "docs/prototype/template.html").read_text()
out = tpl.replace("/*__SEED__*/", json.dumps(seed, separators=(",", ":")))
(root / "docs/prototype/radixark-gtm-os.html").write_text(out)
print("wrote", len(out), "bytes")
