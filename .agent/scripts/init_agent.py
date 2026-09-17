#!/usr/bin/env python3
"""
Agent Protocol Initialization Script

Initialize .agent protocol layer in a new project:
1. Create project instance files
2. Generate AI tool adapter configurations
3. Verify protocol integrity
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def load_template(template_path: Path) -> str:
    """Load template file."""
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


def render_template(template: str, variables: dict[str, Any]) -> str:
    """Render template, replace {{VAR}} style variables."""
    result = template
    for key, value in variables.items():
        pattern = r"\{\{" + re.escape(key) + r"\}\}"
        result = re.sub(pattern, str(value), result)
    return result


def initialize_project_files(agent_dir: Path, config: dict[str, Any]) -> None:
    """Initialize project instance files."""
    project_dir = agent_dir / "project"
    
    # context.md
    context_template = project_dir / "context.md"
    if context_template.exists():
        content = load_template(context_template)
        content = render_template(content, config)
        context_template.write_text(content, encoding="utf-8")
        print(f"  [OK] Updated {context_template}")
    
    # tech-stack.md
    tech_template = project_dir / "tech-stack.md"
    if tech_template.exists():
        content = load_template(tech_template)
        content = render_template(content, config)
        tech_template.write_text(content, encoding="utf-8")
        print(f"  [OK] Updated {tech_template}")


def generate_adapter(
    agent_dir: Path,
    adapter_name: str,
    config: dict[str, Any],
    output_dir: Path,
) -> None:
    """Generate AI tool adapter configuration."""
    adapter_dir = agent_dir / "adapters" / adapter_name
    
    if not adapter_dir.exists():
        print(f"  [WARN] Adapter not found: {adapter_name}")
        return
    
    # Find template files
    templates = list(adapter_dir.glob("*.template.md"))
    
    for template_path in templates:
        template_content = load_template(template_path)
        rendered = render_template(template_content, config)
        
        # Output filename (remove .template)
        output_name = template_path.name.replace(".template", "")
        
        # Determine output location based on adapter type
        if adapter_name == "github-copilot":
            output_path = output_dir / ".github" / output_name
        else:
            output_path = output_dir / f".{adapter_name}" / output_name
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        print(f"  [OK] Generated {output_path}")


def verify_protocol(agent_dir: Path) -> bool:
    """Verify protocol integrity."""
    required_files = [
        "start-here.md",
        "index.md",
        "core/core-rules.md",
        "core/instructions.md",
        "core/conventions.md",
        "project/context.md",
        "project/tech-stack.md",
        "meta/protocol-adr.md",
    ]
    
    missing = []
    for file in required_files:
        if not (agent_dir / file).exists():
            missing.append(file)
    
    if missing:
        print(f"  [FAIL] Missing files: {', '.join(missing)}")
        return False
    
    print("  [OK] All required files present")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Initialize .agent protocol for a new project"
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Project name",
    )
    parser.add_argument(
        "--project-type",
        default="Application",
        help="Project type (Application/Library/CLI)",
    )
    parser.add_argument(
        "--stack",
        default="python",
        choices=["python", "rust", "qt", "typescript", "mixed"],
        help="Primary technology stack",
    )
    parser.add_argument(
        "--adapter",
        action="append",
        default=[],
        help="Generate adapter config (can specify multiple)",
    )
    parser.add_argument(
        "--agent-dir",
        default=".agent",
        help="Path to .agent directory",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for generated files",
    )
    
    args = parser.parse_args()
    
    agent_dir = Path(args.agent_dir)
    output_dir = Path(args.output_dir)
    
    if not agent_dir.exists():
        print(f"Error: .agent directory not found at {agent_dir}")
        sys.exit(1)
    
    # Configuration variables
    config = {
        "PROJECT_NAME": args.project_name,
        "PROJECT_TYPE": args.project_type,
        "PRIMARY_STACK": args.stack,
        "STACK": args.stack,
        "VERSION": "0.1.0",
        "LAST_UPDATE": datetime.now().strftime("%Y-%m-%d"),
        "DATE": datetime.now().strftime("%Y-%m-%d"),
    }
    
    print(f"\n=== Initializing Agent Protocol for '{args.project_name}' ===\n")
    
    # 1. Initialize project files
    print("1. Initializing project files...")
    initialize_project_files(agent_dir, config)
    
    # 2. Generate adapter configurations
    if args.adapter:
        print("\n2. Generating adapter configs...")
        for adapter in args.adapter:
            generate_adapter(agent_dir, adapter, config, output_dir)
    
    # 3. Verify protocol
    print("\n3. Verifying protocol integrity...")
    if not verify_protocol(agent_dir):
        print("\n[WARN] Protocol verification failed!")
        sys.exit(1)
    
    print(f"\n[OK] Agent protocol initialized successfully!")
    print(f"\nNext steps:")
    print(f"  1. Review and update .agent/project/context.md")
    print(f"  2. Review and update .agent/project/tech-stack.md")
    print(f"  3. Read .agent/start-here.md to understand the protocol")


if __name__ == "__main__":
    main()
