#!/usr/bin/env python3
"""
Fix broken EPUB by patching the manifest to reference existing files.
"""
import zipfile
import shutil
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

def fix_epub_manifest(epub_path: str, output_path: str = None):
    """Fix EPUB manifest references to non-existent files."""
    epub_path = Path(epub_path)
    if output_path is None:
        output_path = epub_path.with_suffix('.fixed.epub')
    else:
        output_path = Path(output_path)
    
    # Read the EPUB
    with zipfile.ZipFile(epub_path, 'r') as zf:
        files = zf.namelist()
        print(f"Files in EPUB: {len(files)}")
        
        # Find the OPF file
        opf_path = None
        for name in files:
            if name.endswith('.opf'):
                opf_path = name
                break
        
        if not opf_path:
            print("No OPF file found!")
            return None
        
        print(f"OPF file: {opf_path}")
        
        # Read and parse OPF
        opf_content = zf.read(opf_path).decode('utf-8')
        
        # Parse XML
        try:
            root = ET.fromstring(opf_content)
        except ET.ParseError as e:
            print(f"Parse error: {e}")
            return None
        
        # Find manifest items that don't exist
        ns = {'opf': 'http://www.idpf.org/2007/opf'}
        manifest = root.find('.//opf:manifest', ns)
        
        if manifest is None:
            # Try without namespace
            manifest = root.find('.//manifest')
        
        if manifest is None:
            print("No manifest found!")
            return None
        
        # Find items to remove
        items_to_remove = []
        for item in manifest.findall('opf:item', ns) if manifest.find('opf:item', ns) is not None else manifest.findall('item'):
            href = item.get('href')
            if href:
                full_path = f"{opf_path.rsplit('/', 1)[0]}/{href}" if '/' in opf_path else href
                if full_path not in files:
                    print(f"Missing file: {full_path} (removing from manifest)")
                    items_to_remove.append(item)
        
        if not items_to_remove:
            print("No broken references found - EPUB is fine")
            shutil.copy(epub_path, output_path)
            return output_path
        
        # Remove broken items
        for item in items_to_remove:
            manifest.remove(item)
        
        # Write fixed OPF
        fixed_opf = ET.tostring(root, encoding='unicode')
        
    # Create fixed EPUB
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Extract all files
        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(tmpdir)
        
        # Write fixed OPF
        opf_full_path = tmpdir / opf_path
        with open(opf_full_path, 'w', encoding='utf-8') as f:
            f.write(fixed_opf)
        
        # Create new EPUB
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in tmpdir.rglob('*'):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(tmpdir))
                    zf.write(file_path, arcname)
    
    print(f"Fixed EPUB saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    
    epub_file = './data/input_books/ReturnoftheMountHuaSect.epub'
    output_file = './data/input_books/ReturnoftheMountHuaSect_fixed.epub'
    
    result = fix_epub_manifest(epub_file, output_file)
    if result:
        print(f"\n✓ Successfully fixed EPUB")
        print(f"Original: {epub_file}")
        print(f"Fixed: {result}")
    else:
        print("\n✗ Failed to fix EPUB")
        sys.exit(1)
