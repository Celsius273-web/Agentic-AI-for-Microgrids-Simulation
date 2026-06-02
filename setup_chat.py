#!/usr/bin/env python3
import os
import sys
from shared.rag import initialize_rag_system, search_knowledge_base

def test_rag_system():
    """Test the RAG system functionality."""
    print("\n🔍 Testing RAG System")
    print("=" * 50)
    
    # Initialize RAG system
    docs_dir = "./shared/docs"
    result = initialize_rag_system(docs_dir)
    
    if result["status"] == "error":
        print(f"❌ RAG initialization failed: {result.get('error')}")
        return False
    
    print(f"✅ RAG system initialized successfully")
    print(f"   - Documents loaded: {result['load_result']['loaded_count']} chunks")
    print(f"   - Files processed: {result['load_result']['loaded_files']}")
    
    if result['load_result']['errors']:
        print(f"   - Errors: {result['load_result']['errors']}")
    
    # Test search functionality
    test_queries = [
        "What are the voltage standards for microgrids?",
        "How should batteries be managed?",
        "What are the best practices for solar integration?"
    ]
    
    print("\n🧪 Testing RAG search queries:")
    for query in test_queries:
        print(f"\n   Query: {query}")
        search_result = search_knowledge_base(query, top_k=2)
        
        if search_result["status"] == "success":
            print(f"   ✅ Found {len(search_result['results'])} results")
            for i, result in enumerate(search_result['results'][:1]):  # Show first result
                print(f"      - Score: {result['relevance_score']:.3f}")
                print(f"      - Source: {result['metadata']['source_file']}")
                print(f"      - Section: {result['metadata']['section_header']}")
        else:
            print(f"   ❌ Search failed: {search_result.get('error')}")
    
    return True

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("\n📦 Checking Dependencies")
    print("=" * 50)
    
    required_packages = [
        ("chromadb", "ChromaDB for vector storage"),
        ("sentence_transformers", "Sentence transformers for embeddings"),
        ("fastapi", "FastAPI for web server"),
        ("uvicorn", "Uvicorn ASGI server"),
        ("google.adk", "Google Agent Development Kit")
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - {description}")
        except ImportError:
            print(f"❌ {package} - {description} (MISSING)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def check_file_structure():
    """Check if all required files and directories exist."""
    print("\n📁 Checking File Structure")
    print("=" * 50)
    
    required_paths = [
        ("shared/docs/", "Documentation directory"),
        ("shared/docs/grid_standards.md", "Grid standards documentation"),
        ("shared/docs/best_practices.md", "Best practices documentation"),
        ("shared/docs/past_decisions.md", "Past decisions documentation"),
        ("microgrid_ui/", "React UI directory"),
        ("microgrid_ui/src/ChatInterface.jsx", "Chat interface component"),
        ("chat_server.py", "Chat server implementation"),
        ("shared/rag.py", "RAG system implementation")
    ]
    
    missing_files = []
    
    for path, description in required_paths:
        if os.path.exists(path):
            print(f"✅ {path} - {description}")
        else:
            print(f"❌ {path} - {description} (MISSING)")
            missing_files.append(path)
    
    if missing_files:
        print(f"\n⚠️  Missing files/directories: {', '.join(missing_files)}")
        return False
    
    return True

def main():
    """Main setup function."""
    print("🚀 Microgrid Chat System Setup")
    print("=" * 70)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Setup failed: Missing dependencies")
        sys.exit(1)
    
    # Check file structure
    if not check_file_structure():
        print("\n❌ Setup failed: Missing files")
        sys.exit(1)
    
    # Test RAG system
    if not test_rag_system():
        print("\n❌ Setup failed: RAG system error")
        sys.exit(1)
    
    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Start the chat server:")
    print("   python chat_server.py")
    print("\n2. Start the React UI (in microgrid_ui/ directory):")
    print("   cd microgrid_ui")
    print("   npm install")
    print("   npm start")
    print("\n3. Open browser to: http://localhost:3000")

if __name__ == "__main__":
    main()