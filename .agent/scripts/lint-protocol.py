#!/usr/bin/env python3
"""
Protocol Compliance Linter

Version banner at runtime from cokodo_agent.config when available; else fallback.

Checks:
1. directory-structure  - Standard directories exist
2. required-files       - Required files in project/
3. integrity-violation  - Verify locked files via SHA256 checksums
4. start-here-spec      - start-here.md should not contain project-specific info
5. naming-convention    - kebab-case for .md files
6. internal-links       - Link validity
7. skills-placement     - Project skills must be in _project/
8. engine-pollution     - No hardcoded paths in core/

Commands:
- lint (default)        - Run all checks
- update-checksums      - Update checksums in manifest.json (maintainer only)
"""

import argparse
import hashlib

try:
    from cokodo_agent.config import PROTOCOL_COMPLIANCE_BANNER
except ImportError:
    PROTOCOL_COMPLIANCE_BANNER = "Based on: agent-protocol-rules.md v3.2.1"
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple


class LintResult(NamedTuple):
    """Check result."""
    rule: str
    passed: bool
    message: str
    file: str | None = None
    line: int | None = None


class ProtocolLinter:
    """Protocol linter based on agent-protocol-rules.md."""

    # Locked directories (🔒) - read-only
    LOCKED_DIRS = [
        "core",
        "adapters",
        "meta",
        "scripts",
    ]

    # Locked files at root
    LOCKED_FILES = [
        "start-here.md",
        "manifest.json",
    ]

    # Locked skills (standard skills)
    LOCKED_SKILLS = [
        "agent-governance",
        "ai-integration",
        "guardian",
        "skill-interface.md",
    ]

    # Required files in project/
    REQUIRED_PROJECT_FILES = [
        "context.md",
        "tech-stack.md",
        "known-issues.md",
        "commands.md",
        "deploy.md",
        "session-journal.md",
    ]

    # Standard directory structure
    STANDARD_DIRS = [
        "core",
        "adapters",
        "meta",
        "scripts",
        "skills",
        "project",
    ]

    # Directories to exclude when traversing (third-party/build artifacts)
    IGNORED_DIRS = (".venv", "node_modules", "__pycache__", ".git", "dist", "build")

    def __init__(self, agent_dir: Path):
        self.agent_dir = agent_dir
        self.results: list[LintResult] = []
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        """Load manifest.json."""
        manifest_path = self.agent_dir / "manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return {}

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        content = file_path.read_bytes()
        sha256.update(content)
        return sha256.hexdigest()

    def _is_bytecode_path(self, relative_path: Path) -> bool:
        """Return True for __pycache__ / *.pyc (must not enter checksums or sync)."""
        if relative_path.suffix == ".pyc":
            return True
        return any(part == "__pycache__" for part in relative_path.parts)

    def get_all_locked_files(self) -> list[str]:
        """Get list of all locked file paths (relative to .agent)."""
        locked_files = []

        # Root locked files (except manifest.json which contains checksums)
        for f in self.LOCKED_FILES:
            if f != "manifest.json":  # Skip manifest itself
                path = self.agent_dir / f
                if path.exists():
                    locked_files.append(f)

        # Locked directories
        for locked_dir in self.LOCKED_DIRS:
            dir_path = self.agent_dir / locked_dir
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if not file_path.is_file():
                        continue
                    rel_path = file_path.relative_to(self.agent_dir)
                    if self._is_bytecode_path(rel_path) or self._is_under_ignored_dir(rel_path):
                        continue
                    locked_files.append(str(rel_path).replace("\\", "/"))

        # Locked skills
        skills_dir = self.agent_dir / "skills"
        if skills_dir.exists():
            for skill in self.LOCKED_SKILLS:
                skill_path = skills_dir / skill
                if skill_path.is_file():
                    locked_files.append(f"skills/{skill}")
                elif skill_path.is_dir():
                    for file_path in skill_path.rglob("*"):
                        if not file_path.is_file():
                            continue
                        rel_path = file_path.relative_to(self.agent_dir)
                        if self._is_bytecode_path(rel_path) or self._is_under_ignored_dir(rel_path):
                            continue
                        locked_files.append(str(rel_path).replace("\\", "/"))

        return sorted(set(locked_files))

    def generate_checksums(self) -> dict[str, str]:
        """Generate checksums for all locked files."""
        checksums = {}
        for rel_path in self.get_all_locked_files():
            file_path = self.agent_dir / rel_path
            if file_path.exists():
                checksums[rel_path] = self.compute_sha256(file_path)
        return checksums

    def lint_all(self) -> list[LintResult]:
        """Execute all checks."""
        self.check_directory_structure()
        self.check_required_files()
        self.check_integrity()
        self.check_start_here_spec()
        self.check_naming_convention()
        self.check_skills_placement()
        self.check_engine_pollution()
        self.check_internal_links()
        return self.results

    def check_directory_structure(self) -> None:
        """Check standard directories exist."""
        for dir_name in self.STANDARD_DIRS:
            dir_path = self.agent_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                self.results.append(LintResult(
                    "directory-structure",
                    True,
                    f"Directory exists: {dir_name}/",
                    dir_name,
                ))
            else:
                self.results.append(LintResult(
                    "directory-structure",
                    False,
                    f"Missing standard directory: {dir_name}/",
                    dir_name,
                ))

    def check_required_files(self) -> None:
        """Check required files in project/ directory."""
        project_dir = self.agent_dir / "project"

        if not project_dir.exists():
            self.results.append(LintResult(
                "required-files",
                False,
                "project/ directory does not exist",
                "project",
            ))
            return

        for file_name in self.REQUIRED_PROJECT_FILES:
            file_path = project_dir / file_name
            if file_path.exists():
                self.results.append(LintResult(
                    "required-files",
                    True,
                    f"Required file exists",
                    f"project/{file_name}",
                ))
            else:
                self.results.append(LintResult(
                    "required-files",
                    False,
                    f"Missing required file",
                    f"project/{file_name}",
                ))

        # Also check root required files
        for file_name in self.LOCKED_FILES:
            file_path = self.agent_dir / file_name
            if file_path.exists():
                self.results.append(LintResult(
                    "required-files",
                    True,
                    f"Required file exists",
                    file_name,
                ))
            else:
                self.results.append(LintResult(
                    "required-files",
                    False,
                    f"Missing required file",
                    file_name,
                ))

    def check_integrity(self) -> None:
        """Check integrity of locked files using SHA256 checksums."""
        stored_checksums = self.manifest.get("checksums", {})

        if not stored_checksums:
            self.results.append(LintResult(
                "integrity-violation",
                False,
                "No checksums found in manifest.json. Run 'update-checksums' to generate.",
                "manifest.json",
            ))
            return

        locked_files = self.get_all_locked_files()

        for rel_path in locked_files:
            file_path = self.agent_dir / rel_path

            if rel_path not in stored_checksums:
                # New file not in checksums - could be unauthorized addition
                self.results.append(LintResult(
                    "integrity-violation",
                    False,
                    f"File not in checksums (possibly unauthorized addition)",
                    rel_path,
                ))
                continue

            if not file_path.exists():
                self.results.append(LintResult(
                    "integrity-violation",
                    False,
                    f"Locked file missing",
                    rel_path,
                ))
                continue

            current_hash = self.compute_sha256(file_path)
            expected_hash = stored_checksums[rel_path]

            if current_hash == expected_hash:
                self.results.append(LintResult(
                    "integrity-violation",
                    True,
                    f"Integrity verified",
                    rel_path,
                ))
            else:
                self.results.append(LintResult(
                    "integrity-violation",
                    False,
                    f"File modified (hash mismatch)",
                    rel_path,
                ))

        # Check for files in checksums that no longer exist
        for rel_path in stored_checksums:
            if rel_path not in locked_files:
                file_path = self.agent_dir / rel_path
                if not file_path.exists():
                    self.results.append(LintResult(
                        "integrity-violation",
                        False,
                        f"Locked file deleted",
                        rel_path,
                    ))

    def check_start_here_spec(self) -> None:
        """Check start-here.md does not contain project-specific info."""
        start_here = self.agent_dir / "start-here.md"

        if not start_here.exists():
            return  # Already reported in required-files

        content = start_here.read_text(encoding="utf-8")

        # Patterns that should NOT appear in start-here.md
        forbidden_patterns = [
            (r"^#\s+[A-Z][a-zA-Z0-9_-]+\s*$", "Project name as title"),
            (r"项目概述|Project Overview", "Project overview section"),
            (r"开发状态|Development Status", "Development status"),
            (r"技术栈|Tech Stack", "Tech stack info"),
            (r"目录结构|Directory Structure", "Directory structure"),
            (r"核心数据类型|Core Data Types", "Core data types"),
            (r"常用命令|Common Commands", "Common commands"),
        ]

        found_violation = False
        for pattern, desc in forbidden_patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE))
            if matches:
                found_violation = True
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    self.results.append(LintResult(
                        "start-here-spec",
                        False,
                        f"Should not contain {desc}: '{match.group().strip()}'",
                        "start-here.md",
                        line_num,
                    ))

        if not found_violation:
            self.results.append(LintResult(
                "start-here-spec",
                True,
                "No project-specific content detected",
                "start-here.md",
            ))

    def _is_under_ignored_dir(self, relative_path: Path) -> bool:
        """Return True if path has any ignored directory in its parts."""
        return any(part in self.IGNORED_DIRS for part in relative_path.parts)

    def check_naming_convention(self) -> None:
        """Check kebab-case naming convention for .md files."""
        # kebab-case pattern (allows single word)
        pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.md$")
        # Exceptions (SKILL.md uppercase; adapter templates keep .template.md)
        exceptions = {"MANIFEST.json", "VERSION", "SKILL.md", "README.md"}

        for path in self.agent_dir.rglob("*.md"):
            relative = path.relative_to(self.agent_dir)
            if self._is_under_ignored_dir(relative):
                continue
            if path.name in exceptions or ".template." in path.name:
                continue

            if pattern.match(path.name):
                self.results.append(LintResult(
                    "naming-convention",
                    True,
                    "Follows kebab-case",
                    str(relative),
                ))
            else:
                self.results.append(LintResult(
                    "naming-convention",
                    False,
                    f"Should use kebab-case: {path.name}",
                    str(relative),
                ))

    def check_skills_placement(self) -> None:
        """Check project-specific skills are in _project/ directory."""
        skills_dir = self.agent_dir / "skills"

        if not skills_dir.exists():
            return

        # Get all items directly under skills/
        for item in skills_dir.iterdir():
            if item.name.startswith('.'):
                continue

            relative = item.relative_to(self.agent_dir)

            # Check if it's a standard skill or _project
            if item.name in self.LOCKED_SKILLS or item.name == "_project":
                self.results.append(LintResult(
                    "skills-placement",
                    True,
                    f"Valid skill location",
                    str(relative),
                ))
            else:
                # Non-standard item in skills/ root
                self.results.append(LintResult(
                    "skills-placement",
                    False,
                    f"Project skill must be in skills/_project/: {item.name}",
                    str(relative),
                ))

    def check_engine_pollution(self) -> None:
        """Check for hardcoded paths in locked directories."""
        pollution_patterns = [
            (r"[A-Z]:\\\\", "Windows path"),
            (r"(?<![tT])(?<![pP])(?<![xX])[A-Z]:/", "Windows path"),  # exclude http(s):, ftp:
            (r"/home/\w+/", "Unix home path"),
            (r"/Users/\w+/", "macOS user path"),
            (r"localhost:\d+", "Hardcoded localhost"),
            (r"127\.0\.0\.1:\d+", "Hardcoded IP"),
        ]

        for locked_dir in self.LOCKED_DIRS:
            dir_path = self.agent_dir / locked_dir
            if not dir_path.exists():
                continue

            for path in dir_path.rglob("*.md"):
                relative = path.relative_to(self.agent_dir)
                content = path.read_text(encoding="utf-8")

                found_pollution = False
                for pattern, desc in pollution_patterns:
                    matches = list(re.finditer(pattern, content, re.IGNORECASE))
                    if matches:
                        found_pollution = True
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            self.results.append(LintResult(
                                "engine-pollution",
                                False,
                                f"Found {desc}: {match.group()}",
                                str(relative),
                                line_num,
                            ))

                if not found_pollution:
                    self.results.append(LintResult(
                        "engine-pollution",
                        True,
                        "No pollution detected",
                        str(relative),
                    ))

    def check_internal_links(self) -> None:
        """Check internal link validity."""
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

        for path in self.agent_dir.rglob("*.md"):
            relative = path.relative_to(self.agent_dir)
            if self._is_under_ignored_dir(relative):
                continue
            content = path.read_text(encoding="utf-8")

            for match in link_pattern.finditer(content):
                link_text, link_target = match.groups()

                # Skip external links and anchors
                if link_target.startswith(('http://', 'https://', '#', 'mailto:')):
                    continue

                # Parse relative path (templates/ files: resolve as if deployed to .agent or .agent/project)
                rel_parts = path.relative_to(self.agent_dir).parts
                if link_target.startswith('/'):
                    target_path = self.agent_dir / link_target[1:]
                elif "templates" in rel_parts:
                    base = (self.agent_dir / "project") if "project" in rel_parts else self.agent_dir
                    target_path = (base / link_target).resolve()
                else:
                    target_path = path.parent / link_target

                # Handle anchors in path
                target_str = str(target_path)
                if '#' in target_str:
                    target_path = Path(target_str.split('#')[0])

                line_num = content[:match.start()].count('\n') + 1

                if target_path.exists():
                    self.results.append(LintResult(
                        "internal-links",
                        True,
                        f"Link valid: {link_target}",
                        str(relative),
                        line_num,
                    ))
                elif "core" in rel_parts and (
                    link_target.startswith(("docs/", "doc/")) or link_target in ("CONTRIBUTING.md", "README.md")
                ):
                    # core/ may reference project-root placeholders (e.g. docs/, CONTRIBUTING.md)
                    self.results.append(LintResult(
                        "internal-links",
                        True,
                        f"Optional project placeholder: {link_target}",
                        str(relative),
                        line_num,
                    ))
                else:
                    self.results.append(LintResult(
                        "internal-links",
                        False,
                        f"Broken link: {link_target}",
                        str(relative),
                        line_num,
                    ))


def update_checksums(agent_dir: Path) -> None:
    """Update checksums in manifest.json."""
    manifest_path = agent_dir / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: manifest.json not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    # Load existing manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Generate new checksums
    linter = ProtocolLinter(agent_dir)
    checksums = linter.generate_checksums()

    # Update manifest
    manifest["checksums"] = checksums

    # Write back with proper formatting
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    print(f"Updated checksums for {len(checksums)} locked files:")
    for rel_path in sorted(checksums.keys()):
        print(f"  {rel_path}: {checksums[rel_path][:16]}...")

    print(f"\nChecksums written to {manifest_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Lint .agent protocol compliance (based on agent-protocol-rules.md)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Lint command (default)
    lint_parser = subparsers.add_parser("lint", help="Run compliance checks")
    lint_parser.add_argument(
        "agent_dir",
        nargs="?",
        default=".agent",
        help="Path to .agent directory (default: .agent)",
    )
    lint_parser.add_argument(
        "--rule",
        choices=[
            "directory-structure",
            "required-files",
            "integrity-violation",
            "start-here-spec",
            "naming-convention",
            "internal-links",
            "skills-placement",
            "engine-pollution",
        ],
        help="Check specific rule only",
    )
    lint_parser.add_argument(
        "--format",
        choices=["text", "json", "github"],
        default="text",
        help="Output format (default: text)",
    )

    # Update checksums command
    update_parser = subparsers.add_parser(
        "update-checksums",
        help="Update checksums in manifest.json (maintainer only)"
    )
    update_parser.add_argument(
        "agent_dir",
        nargs="?",
        default=".agent",
        help="Path to .agent directory (default: .agent)",
    )

    args = parser.parse_args()

    # Default to lint if no command specified
    if args.command is None:
        # Re-parse with lint as default
        args.command = "lint"
        args.agent_dir = ".agent"
        args.rule = None
        args.format = "text"

        # Check if first positional arg is a path
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            args.agent_dir = sys.argv[1]

    agent_dir = Path(args.agent_dir)
    if not agent_dir.exists():
        print(f"Error: .agent directory not found at {agent_dir}", file=sys.stderr)
        sys.exit(1)

    if args.command == "update-checksums":
        update_checksums(agent_dir)
        return

    # Lint command
    linter = ProtocolLinter(agent_dir)
    results = linter.lint_all()

    # Filter by rule
    if args.rule:
        results = [r for r in results if r.rule == args.rule]

    # Output results
    errors = [r for r in results if not r.passed]

    if args.format == "json":
        print(json.dumps([r._asdict() for r in results], indent=2, ensure_ascii=False))

    elif args.format == "github":
        # GitHub Actions annotation format
        for r in results:
            if not r.passed:
                file_part = f"file={r.file}" if r.file else ""
                line_part = f",line={r.line}" if r.line else ""
                print(f"::error {file_part}{line_part}::[{r.rule}] {r.message}")
        if not errors:
            print("::notice ::All protocol checks passed")

    else:  # text format
        print("=" * 50)
        print("Protocol Compliance Check")
        print(PROTOCOL_COMPLIANCE_BANNER)
        print("=" * 50)
        print()

        # Group by rule
        rules = sorted(set(r.rule for r in results))
        for rule in rules:
            rule_results = [r for r in results if r.rule == rule]
            passed = sum(1 for r in rule_results if r.passed)
            total = len(rule_results)

            status = "OK" if passed == total else "FAIL"
            print(f"[{status}] {rule}: {passed}/{total} passed")

            # Show errors
            for r in rule_results:
                if not r.passed:
                    loc = f"  {r.file}" if r.file else ""
                    if r.line:
                        loc += f":{r.line}"
                    print(f"    x{loc}: {r.message}")

        print()
        print("=" * 50)
        total_passed = len(results) - len(errors)
        print(f"Total: {total_passed}/{len(results)} passed")

        if errors:
            print(f"\n[FAIL] {len(errors)} error(s) found")
            sys.exit(1)
        else:
            print(f"\n[OK] All checks passed")
            sys.exit(0)


if __name__ == "__main__":
    main()
