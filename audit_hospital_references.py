"""Inventory legacy identifiers without printing credentials or touching submodules."""
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PATTERN = re.compile(
    r'japanese[._ -]?learning|springboot-learning-api|learning-api|'
    r'/api/v1/learning|learning[_-]db|jp[_-]dev|LEARNING_|\blearning\b',
    re.I
)
SKIP_DIRS = {'.git', 'target', 'logs', 'data', 'key', '__pycache__', '.idea', '.codex'}
EVIDENCE = {'REBRANDING-AUDIT.json', 'REBRANDING-CHANGES.json',
            'HOSPITAL-MIGRATION-AUDIT.json', 'HOSPITAL-LEGACY-REFERENCES.json',
            'HOSPITAL-MIGRATION-REPORT.md', 'audit_hospital_references.py',
            'validate_rebranding.py'}
CONTRACT = re.compile(
    r'learning-service|learning-(?:rsa|test)-v\d+|learningservice-[\w.-]+|'
    r'/api/v1/jwks/learning|data[/\\]keys[/\\]learning|'
    r'/run/keys/learning|OWNER=LEARNING|LEARNING for learning-rsa-v1', re.I
)


def main():
    findings = []
    scanned = 0
    for directory, directories, files in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in SKIP_DIRS]
        for name in files:
            if name == 'HOSPITAL-LEGACY-REFERENCES.json':
                continue
            path = Path(directory) / name
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix in {'.log', '.pyc', '.pem', '.jar', '.class'}:
                continue
            try:
                content = path.read_bytes().decode('utf-8-sig')
            except (UnicodeError, PermissionError):
                continue
            scanned += 1
            for number, line in enumerate(content.splitlines(), 1):
                matches = PATTERN.findall(line)
                if not matches:
                    continue
                if relative.startswith('springboot-jwks-api/'):
                    category = 'protected-shared-submodule'
                elif name in EVIDENCE or name == 'SHARED-JWKS-COMPATIBILITY-AUDIT.md':
                    category = 'audit-history-or-migration-evidence'
                elif relative.startswith('observability/phase6-evidence/') or name == '.phase3-state.json':
                    category = 'ignored-historical-runtime-evidence'
                elif CONTRACT.search(line):
                    category = 'preserved-security-contract'
                elif name == '.gitmodules':
                    category = 'unchanged-remote-url'
                elif name == 'HospitalFoundationTest.java' and '/api/v1/learning/me' in line:
                    category = 'retired-route-negative-test'
                elif name == 'InternalJwtAuthenticationTest.java' and '"user", "learning"' in line:
                    category = 'preserved-security-contract'
                elif 'com/japaneselearning/jwks' in line:
                    category = 'protected-shared-source-reference'
                else:
                    category = 'REVIEW'
                findings.append({'file': relative, 'line': number, 'category': category,
                                 'identifiers': sorted(set(matches))})
    report = {'scanned_text_files': scanned,
              'excluded_generated_or_private_directories': sorted(SKIP_DIRS),
              'findings': findings}
    (ROOT / 'HOSPITAL-LEGACY-REFERENCES.json').write_text(json.dumps(report, indent=2) + '\n')
    reviews = [finding for finding in findings if finding['category'] == 'REVIEW']
    print(f'Scanned {scanned} text files; {len(findings)} classified legacy references; {len(reviews)} need review.')
    for finding in reviews[:50]:
        print(f"{finding['file']}:{finding['line']} {finding['identifiers']}")
    if reviews:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
