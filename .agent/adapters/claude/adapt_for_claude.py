#!/usr/bin/env python3
"""
Adapt .agent protocol for Claude Code format

Usage:
    python .agent/adapters/claude/adapt_for_claude.py

Features:
    1. Create .claude/skills/ directory
    2. Copy Skills to .claude/skills/
    3. Ensure SKILL.md has correct YAML frontmatter

Note: Protocol is standardized to use SKILL.md (uppercase), no renaming needed.
"""

import shutil
import re
from pathlib import Path


def extract_first_paragraph(content: str) -> str:
    """Extract first paragraph from markdown content as description."""
    # Skip frontmatter
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            content = content[end + 3:].strip()
    
    # Skip headers
    lines = content.split('\n')
    description_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            if description_lines:
                break
            continue
        if line.startswith('#'):
            continue
        description_lines.append(line)
        if len(' '.join(description_lines)) > 200:
            break
    
    desc = ' '.join(description_lines)
    # Truncate to 1000 chars (with margin)
    if len(desc) > 1000:
        desc = desc[:997] + '...'
    return desc or 'Skill from .agent protocol.'


def sanitize_name(name: str) -> str:
    """Ensure name conforms to Claude requirements: lowercase, numbers, hyphens."""
    # Convert to lowercase
    name = name.lower()
    # Replace underscores and spaces with hyphens
    name = re.sub(r'[_\s]+', '-', name)
    # Keep only lowercase letters, numbers, hyphens
    name = re.sub(r'[^a-z0-9-]', '', name)
    # Truncate to 64 chars
    return name[:64]


def adapt_skill_file(source_file: Path, target_file: Path, skill_name: str) -> None:
    """Adapt a single skill file."""
    content = source_file.read_text(encoding='utf-8')
    
    # Check if frontmatter exists
    has_frontmatter = content.startswith('---')
    
    if has_frontmatter:
        # Extract existing frontmatter
        end = content.find('---', 3)
        if end != -1:
            frontmatter = content[3:end].strip()
            body = content[end + 3:].strip()
            
            # Check if name and description exist
            has_name = 'name:' in frontmatter
            has_desc = 'description:' in frontmatter
            
            if has_name and has_desc:
                # Already complete, just write
                target_file.write_text(content, encoding='utf-8')
                return
            
            # Need to add missing fields
            if not has_name:
                frontmatter = f"name: {sanitize_name(skill_name)}\n" + frontmatter
            if not has_desc:
                desc = extract_first_paragraph(body)
                frontmatter += f"\ndescription: |\n  {desc}"
            
            content = f"---\n{frontmatter}\n---\n\n{body}"
    else:
        # Need to add frontmatter
        safe_name = sanitize_name(skill_name)
        desc = extract_first_paragraph(content)
        
        frontmatter = f"""---
name: {safe_name}
description: |
  {desc}
---

"""
        content = frontmatter + content
    
    target_file.write_text(content, encoding='utf-8')


def adapt_skills(agent_root: Path, claude_root: Path) -> None:
    """Copy and adapt all Skills."""
    agent_skills = agent_root / "skills"
    claude_skills = claude_root / "skills"
    
    if not agent_skills.exists():
        print("[WARN] .agent/skills/ directory not found, skipping")
        return
    
    claude_skills.mkdir(parents=True, exist_ok=True)
    
    for item in agent_skills.iterdir():
        # Skip non-directory files
        if not item.is_dir():
            continue
        
        # Skip special directories
        if item.name.startswith('.') or item.name == '__pycache__':
            continue
        
        skill_name = item.name
        target_dir = claude_skills / skill_name
        
        # Clean target directory
        if target_dir.exists():
            shutil.rmtree(target_dir)
        
        # Copy entire directory
        shutil.copytree(item, target_dir)
        
        # Process entry file (protocol standardized to use SKILL.md)
        skill_file = target_dir / "SKILL.md"
        
        if skill_file.exists():
            # Ensure correct frontmatter
            adapt_skill_file(skill_file, skill_file, skill_name)
            print(f"[OK] Adapted: {skill_name}")
        else:
            print(f"[WARN] Skipped: {skill_name} (no SKILL.md)")


def create_global_rules_reference(agent_root: Path, claude_root: Path) -> None:
    """Create reference file pointing to .agent rules."""
    readme = claude_root / "README.md"
    
    content = """# Claude Skills from .agent Protocol

This directory contains Skills adapted from `.agent` protocol.

## Source Directory

Skills source: `.agent/skills/`

## Update Method

```bash
python .agent/adapters/claude/adapt_for_claude.py
```

## Notes

- Modifications should be made in `.agent/skills/`
- Then run the adapter script to sync to this directory
- Do not modify files in this directory directly

## Related Documentation

- [.agent Protocol Entry](.agent/start-here.md)
- [Claude Skills Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview)
"""
    
    readme.write_text(content, encoding='utf-8')
    print("[OK] Created .claude/README.md")


def main():
    """Main function."""
    # Find .agent directory
    agent_root = Path(".agent")
    claude_root = Path(".claude")
    
    if not agent_root.exists():
        # Try to infer from script location
        script_path = Path(__file__).resolve()
        agent_root = script_path.parent.parent.parent
        claude_root = agent_root.parent / ".claude"
    
    if not agent_root.exists() or not (agent_root / "start-here.md").exists():
        print("[ERROR] Cannot find .agent directory")
        print("   Please run this script from project root")
        return 1
    
    print("Starting .agent to Claude Code adaptation...")
    print(f"   Source: {agent_root.resolve()}")
    print(f"   Target: {claude_root.resolve()}")
    print()
    
    print("Adapting Skills...")
    adapt_skills(agent_root, claude_root)
    print()
    
    print("Creating reference files...")
    create_global_rules_reference(agent_root, claude_root)
    print()
    
    print("[OK] Adaptation complete!")
    print()
    print("Next steps:")
    print("   1. Open project in Claude Code")
    print("   2. Type /skills to view installed skills")
    print("   3. Skills will auto-activate for relevant tasks")
    
    return 0


if __name__ == "__main__":
    exit(main())
