#!/usr/bin/env python3
"""
Test script to verify EPUB RAG MCP Server installation.

This script checks if all dependencies are installed correctly
and if the configuration is valid.
"""
import sys
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing module imports...")
    modules = [
        "mcp",
        "ebooklib",
        "bs4",
        "chromadb",
        "openai",
        "dotenv",
        "tiktoken",
        "tqdm"
    ]

    for module in modules:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except ImportError as e:
            print(f"  ✗ {module}: {e}")
            return False

    return True

def test_config():
    """Test if configuration is valid."""
    print("\nTesting configuration...")
    try:
        from config import Config
        is_valid, error = Config.validate()

        if is_valid:
            print(f"  ✓ Configuration is valid")
            print(f"  ✓ Data directory: {Config.DATA_DIR}")
            print(f"  ✓ Vector DB path: {Config.VECTOR_DB_PATH}")
            return True
        else:
            print(f"  ✗ Configuration error: {error}")
            return False
    except Exception as e:
        print(f"  ✗ Error loading config: {e}")
        return False

def test_components():
    """Test if core components can be initialized."""
    print("\nTesting core components...")
    try:
        from epub_processor import EpubProcessor
        from embedder import Embedder
        from chroma_manager import ChromaManager
        from retriever import Retriever

        print("  ✓ EpubProcessor")
        print("  ✓ Embedder")
        print("  ✓ ChromaManager")
        print("  ✓ Retriever")
        return True
    except Exception as e:
        print(f"  ✗ Error initializing components: {e}")
        return False

def test_data_directory():
    """Test if data directory exists and is writable."""
    print("\nTesting data directory...")
    from config import Config

    data_dir = Config.DATA_DIR
    try:
        data_dir.mkdir(parents=True, exist_ok=True)

        # Test write permission
        test_file = data_dir / "test_write.tmp"
        test_file.write_text("test")
        test_file.unlink()

        print(f"  ✓ Data directory: {data_dir}")
        print("  ✓ Data directory is writable")
        return True
    except Exception as e:
        print(f"  ✗ Error with data directory: {e}")
        return False

def check_epub_files():
    """Check for EPUB files in parent directory."""
    print("\nChecking for EPUB files...")
    parent_dir = Path(__file__).parent.parent

    epub_files = list(parent_dir.glob("*.epub"))
    if epub_files:
        print(f"  ✓ Found {len(epub_files)} EPUB file(s):")
        for epub in epub_files[:3]:  # Show first 3
            print(f"    - {epub.name}")
        if len(epub_files) > 3:
            print(f"    ... and {len(epub_files) - 3} more")
    else:
        print("  ⚠ No EPUB files found in parent directory")
    return True

def main():
    """Run all tests."""
    print("=" * 50)
    print("EPUB RAG MCP Server - Installation Test")
    print("=" * 50)

    tests = [
        test_imports,
        test_config,
        test_components,
        test_data_directory,
        check_epub_files
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    passed = sum(results)
    total = len(results)

    print(f"Tests passed: {passed}/{total}")

    if all(results):
        print("\n✓ All tests passed! The server is ready to use.")
        print("\nNext steps:")
        print("1. Set OPENROUTER_API_KEY in .env file")
        print("2. Run: python server.py")
        print("3. Register the server with Claude Code")
        return 0
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
