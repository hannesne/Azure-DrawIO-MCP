#!/usr/bin/env python3
"""
Analyze differences between DrawIO Azure2 icons and azure_shapes.py

This script fetches the latest icon list from the DrawIO GitHub repository
and compares it with the current azure_shapes.py file to identify:
- New icons available in DrawIO
- Icons we reference that don't exist in DrawIO

Usage:
    python analyze_icons.py
"""

import json
import sys
import urllib.request
from pathlib import Path


def fetch_drawio_icons():
    """Fetch list of Azure2 icons from DrawIO GitHub repository."""
    url = 'https://api.github.com/repos/jgraph/drawio/git/trees/dev?recursive=1'
    
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read())
    
    icons = []
    for item in data['tree']:
        path = item['path']
        if 'src/main/webapp/img/lib/azure2/' in path and path.endswith('.svg'):
            rel_path = path.replace('src/main/webapp/img/lib/azure2/', '')
            icons.append(rel_path)
    
    return sorted(icons)


def load_current_shapes():
    """Load current shape definitions from azure_shapes.py."""
    # Import from the package
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from azure_drawio_mcp_server.azure_shapes import AZURE_SHAPES
    
    current_paths = set()
    for key, (display_name, category, icon_path) in AZURE_SHAPES.items():
        if icon_path:
            current_paths.add(icon_path)
    
    return AZURE_SHAPES, current_paths


def check_for_duplicates():
    """Check azure_shapes.py source file for duplicate keys."""
    import re
    
    shapes_file = Path(__file__).parent.parent.parent.parent / 'azure_drawio_mcp_server' / 'azure_shapes.py'
    
    with open(shapes_file, 'r') as f:
        lines = f.readlines()
    
    seen_keys = {}
    duplicates = []
    in_dict = False
    
    for line_num, line in enumerate(lines, start=1):
        # Detect start of AZURE_SHAPES dictionary
        if 'AZURE_SHAPES' in line and '= {' in line:
            in_dict = True
            continue
        
        # Detect end of dictionary
        if in_dict and line.strip() == '}':
            break
        
        # Parse shape definitions
        if in_dict and ':' in line and not line.strip().startswith('#'):
            # Match pattern: 'Key': ('Name', 'category', 'path.svg'),
            match = re.match(r"\s*'([^']+)':\s*\([^,]+,\s*'[^']+',\s*'([^']+)'\)", line)
            if match:
                key = match.group(1)
                icon_path = match.group(2)
                
                if key in seen_keys:
                    duplicates.append((key, seen_keys[key], (line_num, icon_path)))
                else:
                    seen_keys[key] = (line_num, icon_path)
    
    return duplicates


def main():
    # First check for duplicate keys
    print("Checking for duplicate keys in azure_shapes.py...")
    duplicates = check_for_duplicates()
    
    if duplicates:
        print("\n" + "="*60)
        print(f"❌ ERROR: Found {len(duplicates)} duplicate key(s)!")
        print("="*60)
        for key, (first_line, first_path), (second_line, second_path) in duplicates:
            print(f"\n'{key}':")
            print(f"  First occurrence:  Line {first_line}: {first_path}")
            print(f"  Second occurrence: Line {second_line}: {second_path}")
        print("\n" + "="*60)
        print("When a key appears multiple times in a Python dictionary,")
        print("only the LAST definition is kept. Earlier definitions are")
        print("lost and will be incorrectly reported as 'new' icons.")
        print("\nPlease remove the duplicate definitions.")
        print("="*60)
        sys.exit(1)
    
    print("✓ No duplicate keys found")
    
    print("\nFetching icons from DrawIO repository...")
    drawio_icons = fetch_drawio_icons()
    
    print("Loading current shape definitions...")
    shapes_dict, current_paths = load_current_shapes()
    
    # Analyze
    drawio_set = set(drawio_icons)
    new_icons = sorted(drawio_set - current_paths)
    removed_icons = sorted(current_paths - drawio_set)
    
    # Print summary
    print("\n" + "="*60)
    print(f"DrawIO repository:           {len(drawio_icons)} icons")
    print(f"Current shape definitions:   {len(shapes_dict)} shapes")
    print(f"Unique icon paths used:      {len(current_paths)}")
    print(f"\nNew icons in DrawIO:         {len(new_icons)}")
    print(f"Missing icons we reference:  {len(removed_icons)}")
    print("="*60)
    
    if new_icons:
        print(f"\nNEW ICONS IN DRAWIO ({len(new_icons)} total):")
        for icon_path in new_icons:
            print(f"  {icon_path}")
    else:
        print("\n✓ All DrawIO icons are covered!")
    
    if removed_icons:
        print(f"\nWARNING: Icons in azure_shapes.py not in DrawIO ({len(removed_icons)} total):")
        for icon_path in removed_icons:
            # Find which shape uses this
            for key, (display_name, category, path) in shapes_dict.items():
                if path == icon_path:
                    print(f"  {icon_path:50s} (used by {key})")
                    break


if __name__ == '__main__':
    main()
