import json
from pathlib import Path

folder = Path('data/raw/meta')
files = list(folder.glob('*/*.json'))

all_rows = []

for file in files:
    with open(file) as f:
        content = json.load(f)
    rows = content['data']
    all_rows.extend(rows)

print(len(files), "files")
print(len(all_rows), "rows")