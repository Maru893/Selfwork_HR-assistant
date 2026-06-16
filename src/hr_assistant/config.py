# config.py
import os

class Config:
    DOCUMENTS_DIR = "resumes"
    COLLECTION_NAME = "CVs"
    PERSISTENT_DIR = "data/chromadb" 
    
    # Embedding (OpenAI)
    MODEL_NAME = "text-embedding-3-small"
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")

    # Chunking
    CHUNKING_STRATEGY = "fixed"
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 150

    

    ### Configurazione per Ollama locale (Llama 3.2)
    LLM_MODEL = "llama3.2"  
    AI_API_URL = "http://localhost:11434/v1"
    AI_API_KEY = "ollama"
    
    ### Configurazione per OpenAI cloud (GPT-4o-mini)

    # LLM_MODEL = "gpt-4o-mini"
    # AI_API_URL = "https://openai.com/v1"
    # AI_API_KEY = os.getenv("OPENAI_API_KEY")

    
