import os
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import re

class MicrogridRAG:
    """
    Retrieval-Augmented Generation system for microgrid documentation and best practices.
    Uses ChromaDB for vector storage and sentence-transformers for embeddings.
    """
    
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "microgrid_docs"):
        """
        Initialize the RAG system with ChromaDB and embedding model.
        
        Args:
            db_path: Path to store ChromaDB data
            collection_name: Name of the collection to store documents
        """
        self.db_path = db_path
        self.collection_name = collection_name
        
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        print("Loading sentence transformer model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("Model loaded successfully")
        
        try:
            self.collection = self.client.get_collection(collection_name)
            print(f"Using existing collection: {collection_name}")
        except:
            print(f"Creating new collection: {collection_name}")
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Microgrid documentation and best practices"}
            )
        
        self.loaded_files = set()
        
    def load_documents_from_directory(self, docs_dir: str) -> Dict[str, Any]:
        """
        Load all markdown documents from the specified directory.
        
        Args:
            docs_dir: Directory containing markdown files
            
        Returns:
            Dict with loading results and statistics
        """
        if not os.path.exists(docs_dir):
            return {
                "status": "error",
                "error": f"Directory not found: {docs_dir}",
                "loaded_count": 0
            }
        
        loaded_count = 0
        errors = []
        
        for filename in os.listdir(docs_dir):
            if filename.endswith('.md'):
                file_path = os.path.join(docs_dir, filename)
                
                try:
                    result = self.load_document(file_path)
                    if result["status"] == "success":
                        loaded_count += result["chunks_added"]
                        self.loaded_files.add(filename)
                    else:
                        errors.append(f"{filename}: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
        
        return {
            "status": "success" if loaded_count > 0 else "error",
            "loaded_count": loaded_count,
            "loaded_files": list(self.loaded_files),
            "errors": errors,
            "collection_size": self.collection.count()
        }
    
    def load_document(self, file_path: str) -> Dict[str, Any]:
        """
        Load a single markdown document into the RAG system.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            Dict with loading results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            chunks = self._chunk_document(content, file_path)
            
            if not chunks:
                return {
                    "status": "error",
                    "error": "No valid chunks extracted from document",
                    "chunks_added": 0
                }
            
            texts = [chunk["text"] for chunk in chunks]
            embeddings = self.embedding_model.encode(texts).tolist()
            ids = [chunk["id"] for chunk in chunks]
            metadatas = [chunk["metadata"] for chunk in chunks]
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )
            
            return {
                "status": "success",
                "chunks_added": len(chunks),
                "file_path": file_path
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "chunks_added": 0
            }
    
    def _chunk_document(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Split document content into meaningful chunks for embedding.
        
        Args:
            content: Document content
            file_path: Source file path
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        sections = re.split(r'\n(?=#{2,3} )', content)
        
        filename = os.path.basename(file_path)
        base_id = filename.replace('.md', '').replace(' ', '_')
        
        for i, section in enumerate(sections):
            if not section.strip():
                continue
                
            lines = section.strip().split('\n')
            if lines[0].startswith('#'):
                header = lines[0].replace('#', '').strip()
                section_content = '\n'.join(lines[1:]).strip()
            else:
                header = "Introduction"
                section_content = section.strip()
            
            if len(section_content) < 50:
                continue

            paragraphs = section_content.split('\n\n')
            current_chunk = ""
            chunk_count = 0
            
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                
                if current_chunk and len(current_chunk + paragraph) > 1000:
                    chunk_id = f"{base_id}_section_{i}_chunk_{chunk_count}"
                    chunks.append({
                        "id": chunk_id,
                        "text": f"# {header}\n\n{current_chunk}",
                        "metadata": {
                            "source_file": filename,
                            "section_header": header,
                            "chunk_index": chunk_count,
                            "section_index": i,
                            "loaded_at": datetime.now(timezone.utc).isoformat()
                        }
                    })
                    current_chunk = paragraph
                    chunk_count += 1
                else:
                    current_chunk += "\n\n" + paragraph if current_chunk else paragraph
            
            if current_chunk:
                chunk_id = f"{base_id}_section_{i}_chunk_{chunk_count}"
                chunks.append({
                    "id": chunk_id,
                    "text": f"# {header}\n\n{current_chunk}",
                    "metadata": {
                        "source_file": filename,
                        "section_header": header,
                        "chunk_index": chunk_count,
                        "section_index": i,
                        "loaded_at": datetime.now(timezone.utc).isoformat()
                    }
                })
        
        return chunks
    
    def search_docs(self, query_text: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Search the knowledge base for relevant documents.
        
        Args:
            query_text: Natural language query
            top_k: Number of top results to return (default 3)
            
        Returns:
            Dict containing search results with scores
        """
        try:
            if self.collection.count() == 0:
                return {
                    "status": "error",
                    "error": "No documents loaded in knowledge base",
                    "results": [],
                    "query": query_text
                }
            
            query_embedding = self.embedding_model.encode([query_text]).tolist()[0]
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self.collection.count())
            )
            
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i] if results['distances'] else None,
                        "relevance_score": 1 - results['distances'][0][i] if results['distances'] else 1.0
                    })
            
            return {
                "status": "success",
                "results": formatted_results,
                "query": query_text,
                "total_docs": self.collection.count(),
                "search_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "results": [],
                "query": query_text
            }
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about the current collection.
        
        Returns:
            Dict with collection statistics
        """
        try:
            count = self.collection.count()
            return {
                "status": "success",
                "collection_name": self.collection_name,
                "document_count": count,
                "loaded_files": list(self.loaded_files),
                "db_path": self.db_path
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

_rag_instance = None

def get_rag_instance() -> MicrogridRAG:
    """Get or create the global RAG instance."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = MicrogridRAG()
    return _rag_instance

def initialize_rag_system(docs_dir: str = "./shared/docs") -> Dict[str, Any]:
    """
    Initialize the RAG system and load documents.
    
    Args:
        docs_dir: Directory containing documentation files
        
    Returns:
        Initialization results
    """
    try:
        rag = get_rag_instance()
        
        load_result = rag.load_documents_from_directory(docs_dir)
        
        return {
            "status": "success",
            "rag_initialized": True,
            "load_result": load_result,
            "initialized_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "rag_initialized": False
        }

def search_knowledge_base(query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Search the RAG knowledge base.
    
    Args:
        query: Search query
        top_k: Number of results to return
        
    Returns:
        Search results
    """
    rag = get_rag_instance()
    return rag.search_docs(query, top_k)