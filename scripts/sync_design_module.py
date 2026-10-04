"""Distribute the single shared source to host release directories.

No database or design-content files are touched. --check is read-only.
Aidat writes require the workspace's external-directory permission.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'shared/toya-design'

def distribution(host: str, aidat: Path):
    for src in sorted(SOURCE.rglob('*')):
        if not src.is_file():
            continue
        rel = src.relative_to(SOURCE)
        if host == 'aidat':
            target = aidat / 'modules/toya-design' / rel
        elif rel.parts[0] == 'assets':
            target = ROOT / 'portal/public/assets/design' / Path(*rel.parts[1:])
        else:
            target = ROOT / 'portal/src/design' / rel
        yield src, target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['portal', 'aidat', 'both'], default='portal')
    parser.add_argument('--aidat-root', type=Path, default=Path('C:/xampp/htdocs/toya'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    mismatches = []
    for host in (['portal','aidat'] if args.host == 'both' else [args.host]):
        for src, dst in distribution(host, args.aidat_root):
            if dst.is_file() and src.read_bytes() == dst.read_bytes():
                continue
            mismatches.append(str(dst))
            if not args.check:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    print(json.dumps({'mode': 'check' if args.check else 'sync', 'changed_or_different': mismatches}, ensure_ascii=False))
    return 1 if args.check and mismatches else 0

if __name__ == '__main__':
    raise SystemExit(main())
