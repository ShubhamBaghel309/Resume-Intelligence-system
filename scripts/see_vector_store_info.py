import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.vectorstore.chroma_store import ResumeVectorStore

vector_store = ResumeVectorStore(persist_directory="storage/chroma")
all_docs = vector_store.collection.get(include=['metadatas', 'documents'])

for i, doc in enumerate(all_docs['documents']):
    print(f"\n--- Chunk {i+1} ---")
    print(doc)
    print("Metadata:", all_docs['metadatas'][i])