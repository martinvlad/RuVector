"""Execute the published Python quickstarts against installed distributions."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

base = Path(__file__).resolve().parent
count = 0
for readme in sorted(base.glob('ruvector-*/README.md')):
    for code in re.findall(r'```python\n(.*?)```', readme.read_text(), re.S):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([sys.executable, '-c', code], cwd=directory,
                           stdin=subprocess.DEVNULL, check=True, timeout=30)
        count += 1
        print(f'{readme.parent.name}: quickstart passed')
if count != 11:
    raise ValueError(f'Expected eleven executable package quickstarts, found {count}')
