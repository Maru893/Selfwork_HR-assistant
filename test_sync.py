# file di test per verifica logica

from hr_assistant.database import Database
from hr_assistant.document_processor import DocumentProcessor


db = Database()

report = DocumentProcessor.process_documents(db)

print("Report sincronizzazione:")
print(report)

print()
print("Chunk totali in ChromaDB:")
print(db.count())

print()
print("File tracciati:")
print(db.get_tracked_files())