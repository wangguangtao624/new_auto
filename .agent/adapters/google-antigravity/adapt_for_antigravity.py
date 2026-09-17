#!/usr/bin/env python3
"""
Adapt .agent protocol for Google Antigravity format

Usage:
    python .agent/adapters/google-antigravity/adapt_for_antigravity.py

Features:
    1. Ensure SKILL.md has correct YAML frontmatter
    2. Create rules reference files in .agent/rules/

Note: Protocol is standardized to use SKILL.md (uppercase), no renaming needed.
"""

import os
import re
from pathlib import Path


def extract_description_from_content(content: str) -> str:
    """Extract description from markdown content."""
    # Try to extract first paragraph as description
    lines = content.split('\n')
    description_lines = []
    in_content = False
    
    for line in lines:
        # Skip frontmatter
        if line.strip() == '---':
            continue
        # Skip headers
        if line.startswith('#'):
            in_content = True
            continue
        # Collect non-empty lines as description
        if in_content and line.strip():
            description_lines.append(line.strip())
            if len(description_lines) >= 2:
                break
    
    return ' '.join(description_lines) if description_lines else 'Please update this description.'


def adapt_skills(agent_root: Path) -> None:
    """Ensure SKILL.md has correct YAML frontmatter."""
    skills_dir = agent_root / "skills"
    
    if not skills_dir.exists():
        print("[WARN] skills/ directory not found, skipping")
        return
    
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        
        # Skip non-skill directories
        if skill_dir.name in ('__pycache__', '.git'):
            continue
        
        skill_file = skill_dir / "SKILL.md"
        
        # Protocol standardized to use SKILL.md
        if not skill_file.exists():
            print(f"[WARN] Skipped: {skill_dir.name} (no SKILL.md)")
            continue
        
        content = skill_file.read_text(encoding='utf-8')
        
        # Check if frontmatter exists
        if content.startswith('---'):
            print(f"[OK] Ready: {skill_dir.name}")
            continue
        
        # Add frontmatter
        skill_name = skill_dir.name
        description = extract_description_from_content(content)
        
        frontmatter = f"""---
name: {skill_name}
description: |
  {description}
---

"""
        content = frontmatter + content
        skill_file.write_text(content, encoding='utf-8')
        print(f"[OK] Added frontmatter: {skill_dir.name}")


def create_rules_references(agent_root: Path) -> None:
    """Create rules reference files."""
    rules_dir = agent_root / "rules"
    rules_dir.mkdir(exist_ok=True)
    
    # Core rules file mapping
    mappings = {
        "core-rules.md": {
            "source": "core/core-rules.md",
            "title": "Core Rules",
            "activation": "Always On"
        },
        "instructions.md": {
            "source": "core/instructions.md",
            "title": "AI Collaboration Guidelines",
            "activation": "Always On"
        },
        "conventions.md": {
            "source": "core/conventions.md",
            "title": "Naming and Git Conventions",
            "activation": "Model Decision"
        },
        "security.md": {
            "source": "core/security.md",
            "title": "Security Development Standards",
            "activation": "Manual"
        },
    }
    
    for rule_name, config in mappings.items():
        target = rules_dir / rule_name
        if not target.exists():
            content = f"""# {config['title']}

> Activation Mode: {config['activation']}

For detailed rules, please refer to:

@.agent/{config['source']}
"""
            target.write_text(content, encoding='utf-8')
            print(f"[OK] Created rule: {rule_name}")
        else:
            print(f"[SKIP] Rule exists: {rule_name}")


def create_project_rule(agent_root: Path) -> None:
    """Create project context rule."""
    rules_dir = agent_root / "rules"
    rules_dir.mkdir(exist_ok=True)
    
    project_rule = rules_dir / "project-context.md"
    if not project_rule.exists():
        content = """# Project Context

> Activation Mode: Always On

Project business context and tech stack information:

@.agent/project/context.md
@.agent/project/tech-stack.md
@.agent/project/known-issues.md
"""
        project_rule.write_text(content, encoding='utf-8')
        print("[OK] Created rule: project-context.md")


def create_readme(agent_root: Path) -> None:
    """Create README in rules directory."""
    rules_dir = agent_root / "rules"
    readme = rules_dir / "README.md"
    
    if not readme.exists():
        content = """# Antigravity Rules

This directory contains workspace rules for Google Antigravity.

## Rules Description

| File | Description | Activation Mode |
|------|-------------|-----------------|
| `core-rules.md` | Core development rules | Always On |
| `instructions.md` | AI collaboration guidelines | Always On |
| `conventions.md` | Naming and Git conventions | Model Decision |
| `security.md` | Security development standards | Manual (@security) |
| `project-context.md` | Project context | Always On |

## Activation Modes

- **Always On**: Always applied
- **Manual**: Manually activate using @rule-name in conversation
- **Model Decision**: Model decides whether to apply based on task
- **Glob**: Applied when matching specific file types

## More Information

See [Google Antigravity Rules Documentation](https://antigravity.google/docs/rules-workflows)
"""
        readme.write_text(content, encoding='utf-8')
        print("[OK] Created rules/README.md")


def main():
    """Main function."""
    # Find .agent directory
    agent_root = Path(".agent")
    if not agent_root.exists():
        # Try to infer from script location
        script_path = Path(__file__).resolve()
        agent_root = script_path.parent.parent.parent
    
    if not agent_root.exists() or not (agent_root / "start-here.md").exists():
        print("[ERROR] Cannot find .agent directory")
        print("   Please run this script from project root")
        return 1
    
    print("Starting .agent to Google Antigravity adaptation...")
    print(f"   Target: {agent_root.resolve()}")
    print()
    
    print("Adapting Skills...")
    adapt_skills(agent_root)
    print()
    
    print("Creating Rules references...")
    create_rules_references(agent_root)
    create_project_rule(agent_root)
    create_readme(agent_root)
    print()
    
    print("[OK] Adaptation complete!")
    print()
    print("Next steps:")
    print("   1. Open project in Antigravity")
    print("   2. Check Customizations > Rules to confirm rules are loaded")
    print("   3. Check Skills panel to confirm skills are recognized")
    print("   4. Adjust activation modes as needed")
    
    return 0


if __name__ == "__main__":
    exit(main())
