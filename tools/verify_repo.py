from pathlib import Path

required = {
    "README.md": ["Capability does not imply permission", "Initial roadmap"],
    "AGENTS.md": ["tools/dev/check", "UNKNOWN"],
    "docs/architecture.md": ["execution/governance plane", "Timeweb", "Neon", "Langfuse"],
}

for name, needles in required.items():
    path = Path(name)
    if not path.is_file():
        raise SystemExit(f"missing required file: {name}")
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"{name}: missing invariant: {needle}")

print("REPO_VERIFY_PASS")
