#!/usr/bin/env python3
"""
Token Counter Script

Analyze token usage in .agent protocol documents to help optimize protocol size.

Note: Uses simple token estimation method (words + punctuation).
Actual token count depends on the specific tokenizer.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileStats:
    """File statistics."""
    path: str
    chars: int
    words: int
    lines: int
    tokens_estimate: int


def estimate_tokens(text: str) -> int:
    """
    Estimate token count.
    
    Simple estimation method:
    - English: ~1 token / 4 chars
    - Chinese: ~1 token / 2 chars
    - Code/punctuation: additional count
    
    This is a rough estimate. Use tiktoken or similar for accuracy.
    """
    # Separate Chinese and English
    chinese = re.findall(r'[\u4e00-\u9fff]', text)
    english_words = re.findall(r'[a-zA-Z]+', text)
    numbers = re.findall(r'\d+', text)
    punctuation = re.findall(r'[^\w\s]', text)
    
    # Estimate
    chinese_tokens = len(chinese) * 1.5  # Chinese chars typically 1-2 tokens
    english_tokens = sum(max(1, len(w) / 4) for w in english_words)
    number_tokens = len(numbers)
    punct_tokens = len(punctuation) * 0.5
    
    return int(chinese_tokens + english_tokens + number_tokens + punct_tokens)


def analyze_file(path: Path, base_dir: Path) -> FileStats:
    """Analyze a single file."""
    content = path.read_text(encoding="utf-8")
    
    return FileStats(
        path=str(path.relative_to(base_dir)),
        chars=len(content),
        words=len(content.split()),
        lines=content.count('\n') + 1,
        tokens_estimate=estimate_tokens(content),
    )


def analyze_directory(agent_dir: Path) -> dict[str, list[FileStats]]:
    """Analyze directory."""
    results: dict[str, list[FileStats]] = {}
    
    for path in agent_dir.rglob("*.md"):
        relative = path.relative_to(agent_dir)
        
        # Group by top-level directory
        if len(relative.parts) > 1:
            category = relative.parts[0]
        else:
            category = "root"
        
        if category not in results:
            results[category] = []
        
        results[category].append(analyze_file(path, agent_dir))
    
    return results


def format_size(size: int) -> str:
    """Format size for display."""
    if size < 1000:
        return str(size)
    elif size < 1000000:
        return f"{size/1000:.1f}K"
    else:
        return f"{size/1000000:.1f}M"


def main():
    parser = argparse.ArgumentParser(description="Count tokens in .agent protocol")
    parser.add_argument(
        "--agent-dir",
        default=".agent",
        help="Path to .agent directory",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--sort",
        choices=["path", "tokens", "chars"],
        default="tokens",
        help="Sort by",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Show only top N files",
    )
    
    args = parser.parse_args()
    
    agent_dir = Path(args.agent_dir)
    if not agent_dir.exists():
        print(f"Error: .agent directory not found at {agent_dir}")
        sys.exit(1)
    
    results = analyze_directory(agent_dir)
    
    # Aggregate statistics
    all_files: list[FileStats] = []
    for category_files in results.values():
        all_files.extend(category_files)
    
    # Sort
    sort_key = {
        "path": lambda x: x.path,
        "tokens": lambda x: -x.tokens_estimate,
        "chars": lambda x: -x.chars,
    }[args.sort]
    all_files.sort(key=sort_key)
    
    if args.top > 0:
        all_files = all_files[:args.top]
    
    # Output
    if args.format == "json":
        import json
        output = {
            "files": [vars(f) for f in all_files],
            "summary": {
                "total_files": len(all_files),
                "total_tokens": sum(f.tokens_estimate for f in all_files),
                "total_chars": sum(f.chars for f in all_files),
            }
        }
        print(json.dumps(output, indent=2))
    
    elif args.format == "csv":
        print("path,chars,words,lines,tokens_estimate")
        for f in all_files:
            print(f"{f.path},{f.chars},{f.words},{f.lines},{f.tokens_estimate}")
    
    else:
        print("=== Token Statistics ===\n")
        
        # Summary by category
        print("By Category:")
        print("-" * 50)
        for category in sorted(results.keys()):
            files = results[category]
            total_tokens = sum(f.tokens_estimate for f in files)
            total_chars = sum(f.chars for f in files)
            print(f"  {category:20} {len(files):3} files  "
                  f"{format_size(total_tokens):>8} tokens  "
                  f"{format_size(total_chars):>8} chars")
        
        print("\nTop Files by Tokens:")
        print("-" * 50)
        
        display_files = all_files[:10] if args.top == 0 else all_files
        for f in display_files:
            print(f"  {f.path:40} {format_size(f.tokens_estimate):>8} tokens")
        
        # Total
        total_tokens = sum(f.tokens_estimate for f in all_files)
        total_chars = sum(f.chars for f in all_files)
        total_lines = sum(f.lines for f in all_files)
        
        print("\n" + "=" * 50)
        print(f"Total: {len(all_files)} files")
        print(f"  Tokens (estimated): {format_size(total_tokens)}")
        print(f"  Characters: {format_size(total_chars)}")
        print(f"  Lines: {format_size(total_lines)}")
        
        # Token budget advice
        print("\nToken Budget Analysis:")
        if total_tokens < 5000:
            print("  [OK] Small protocol - suitable for single-context loading")
        elif total_tokens < 10000:
            print("  [WARN] Medium protocol - consider selective loading")
        else:
            print("  [LARGE] Large protocol - requires on-demand loading strategy")


if __name__ == "__main__":
    main()
