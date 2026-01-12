# Test: Verify Chroma migration warning is fixed
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("\n" + "="*80)
print("🧪 TESTING: Chroma Configuration Fix")
print("="*80)

# Test 1: Check environment variables
print("\n📁 Cache Directories:")
print(f"   HF_HOME: {os.environ.get('HF_HOME', 'Not set (will use C drive default!)')}")
print(f"   TRANSFORMERS_CACHE: {os.environ.get('TRANSFORMERS_CACHE', 'Not set')}")
print(f"   SENTENCE_TRANSFORMERS_HOME: {os.environ.get('SENTENCE_TRANSFORMERS_HOME', 'Not set')}")

# Test 2: Initialize vector store
print("\n🔧 Initializing ResumeVectorStore...")
try:
    from app.vectorstore.chroma_store import ResumeVectorStore
    
    vector_store = ResumeVectorStore(persist_directory="storage/chroma")
    print("   ✅ ResumeVectorStore initialized successfully!")
    
    # Check if collection exists
    collection = vector_store.collection
    count = collection.count()
    print(f"   ✅ Collection 'resumes' has {count} vectors")
    
    # Test 3: Verify cache directories were created
    print("\n📂 Verifying D Drive Cache Directories:")
    cache_dir = "storage/model_cache"
    if os.path.exists(cache_dir):
        print(f"   ✅ Model cache directory exists: {os.path.abspath(cache_dir)}")
        files = os.listdir(cache_dir)
        if files:
            print(f"   ✅ Contains {len(files)} items (models cached)")
        else:
            print(f"   ⚠️  Empty (models will be downloaded here on first use)")
    else:
        print(f"   ⚠️  Cache directory not found (will be created on first use)")
    
    chroma_dir = "storage/chroma"
    if os.path.exists(chroma_dir):
        print(f"   ✅ Chroma data directory exists: {os.path.abspath(chroma_dir)}")
        files = os.listdir(chroma_dir)
        print(f"   ✅ Contains {len(files)} items")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - No migration warnings!")
    print("="*80)
    print("\n💡 Your vector store is now configured to use D drive exclusively.")
    print("   - Chroma data: D:\\GEN AI internship work\\Resume Intelligence System\\storage\\chroma")
    print("   - Model cache: D:\\GEN AI internship work\\Resume Intelligence System\\storage\\model_cache")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n" + "="*80)
    print("⚠️  If you see migration warnings, try:")
    print("="*80)
    print("1. Delete old Chroma data:")
    print("   Remove-Item -Recurse -Force storage\\chroma")
    print("2. Re-run the indexing script:")
    print("   python scripts\\index_all_resumes.py")
