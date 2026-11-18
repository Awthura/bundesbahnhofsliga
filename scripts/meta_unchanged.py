"""Exit 0 if docs/data/meta.json equals the committed version apart from the build time."""
import json
import subprocess
import sys

old = subprocess.run(["git", "show", "HEAD:docs/data/meta.json"], capture_output=True, text=True).stdout
new = open("docs/data/meta.json").read()
try:
    old, new = json.loads(old), json.loads(new)
except ValueError:
    sys.exit(1)
old.pop("generated", None)
new.pop("generated", None)
sys.exit(0 if old == new else 1)
