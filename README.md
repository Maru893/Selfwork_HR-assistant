# HR Assistant

Questo progetto si chiama `hr-assistant`.

È un assistente HR sviluppato in Python 3.12 con Poetry. Il suo scopo è aiutare a cercare candidati dentro una raccolta di CV in formato `.txt`.

Il progetto usa un approccio RAG, cioè Retrieval Augmented Generation. In parole semplici, prima cerca le parti più utili nei CV e poi usa un modello di linguaggio per generare una risposta più chiara.

L'interfaccia è fatta con Chainlit, quindi posso usare il progetto come una piccola chat.

## Obiettivo del progetto

L'obiettivo è costruire un assistente che possa rispondere a domande come:

```text
Chi è il candidato migliore per un ruolo da software engineer?
```

```text
Cerco una persona con esperienza in cybersecurity.
```

```text
Quale candidato ha competenze in automazione dei processi operativi?
```

Il sistema cerca nei CV indicizzati, recupera il testo più rilevante e poi genera una risposta usando il modello LLM configurato.

## Tecnologie usate

Le tecnologie principali sono:

* Python 3.12
* Poetry, per gestire il progetto e le dipendenze
* Chainlit, per creare l'interfaccia chat
* ChromaDB, per salvare e cercare i vettori
* OpenAI embeddings, per trasformare i testi in vettori
* Ollama, per usare un modello locale come Llama 3.2
* OpenAI, come alternativa cloud per il completamento
* LangChain OpenAI, per il chunking semantico
* Scikit learn, per calcolare la similarità coseno
* NumPy, per calcolare il percentile nel chunking semantico

## Struttura del progetto

La struttura principale del progetto è questa:

```text
hr-assistant/
├── pyproject.toml
├── README.md
├── resumes/
├── data/
│   └── chromadb/
└── src/
    └── hr_assistant/
        ├── __init__.py
        ├── config.py
        ├── database.py
        ├── document_processor.py
        ├── chunking.py
        └── utils.py
```

## Cosa contiene ogni file

### config.py

Questo file contiene le impostazioni principali del progetto.

Qui vengono configurati:

* la cartella dei CV
* il nome della collection ChromaDB
* la cartella di persistenza di ChromaDB
* il modello embedding
* la chiave OpenAI
* il modello LLM
* l'URL delle API
* la strategia di chunking

Esempio:

```python
class Config:
    DOCUMENTS_DIR = "resumes"
    COLLECTION_NAME = "CVs"
    PERSISTENT_DIR = "data/chromadb"

    MODEL_NAME = "text-embedding-3-small"
    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "IL_TUO_TOKEN_OPENAI")

    CHUNKING_STRATEGY = "semantic"
    CHUNK_SIZE = 900
    CHUNK_OVERLAP = 150

    SEMANTIC_BREAKPOINT_PERCENTILE = 90
    SEMANTIC_BUFFER_SIZE = 1
    SEMANTIC_MIN_CHUNK_SIZE = 250

    LLM_MODEL = "llama3.2"
    AI_API_URL = "http://localhost:11434/v1"
    AI_API_KEY = "ollama"
```

In questo progetto ho separato il modello embedding dal modello LLM.

Il modello embedding serve a trasformare i CV in vettori.

Il modello LLM serve a generare le risposte nella chat.

## database.py

Questo file gestisce ChromaDB.

ChromaDB è il database vettoriale del progetto. Non salva solo testo, ma salva anche gli embedding, cioè una rappresentazione numerica del significato del testo.

Il database usa:

```python
chromadb.PersistentClient(path=Config.PERSISTENT_DIR)
```

Questo significa che i dati vengono salvati su disco dentro:

```text
data/chromadb
```

Quindi, quando riavvio il progetto, non devo ricaricare tutti i CV da zero.

Le funzioni principali sono:

```python
add_documents()
```

Aggiunge i chunk dentro ChromaDB.

```python
query()
```

Cerca i chunk più simili alla domanda dell'utente.

```python
get_tracked_files()
```

Legge i file già indicizzati.

```python
remove_document_by_source()
```

Rimuove da ChromaDB tutti i chunk di un file specifico.

```python
count()
```

Conta quanti chunk sono presenti nel database.

```python
reset()
```

Svuota la collection e la ricrea.

## document_processor.py

Questo file si occupa dei documenti.

Il suo compito è:

* leggere i file `.txt`
* calcolare l'hash del file
* estrarre metadata utili
* dividere il testo in chunk
* sincronizzare la cartella `resumes` con ChromaDB

La sincronizzazione è una parte importante del progetto.

Prima il progetto caricava i documenti solo se il database era vuoto.

Adesso invece fa un confronto intelligente.

## Sincronizzazione dei documenti

La funzione principale è:

```python
DocumentProcessor.process_documents(db)
```

Questa funzione controlla i file presenti nella cartella:

```text
resumes
```

Poi controlla i file già presenti in ChromaDB.

A quel punto divide i file in quattro casi.

### File nuovo

Il file è nella cartella `resumes`, ma non è ancora in ChromaDB.

Il sistema lo indicizza.

### File modificato

Il file è già in ChromaDB, ma il suo hash è cambiato.

Il sistema elimina i vecchi chunk e indicizza di nuovo il file aggiornato.

### File eliminato

Il file era in ChromaDB, ma non esiste più nella cartella `resumes`.

Il sistema elimina i chunk collegati a quel file.

### File invariato

Il file è nella cartella ed è già in ChromaDB con lo stesso hash.

Il sistema non fa nulla.

Questa logica evita di ricalcolare embedding inutili.

## Hash dei file

Per capire se un file è cambiato, uso un hash.

L'hash è come un'impronta digitale del file.

Se cambio anche una piccola parte del file, l'hash cambia.

Questo permette al sistema di capire quali CV devono essere aggiornati.

## Metadata dei candidati

Durante l'indicizzazione, il progetto prova anche a estrarre alcune informazioni dal CV.

Le informazioni estratte sono:

* nome del candidato
* email
* numero di telefono
* nome del file
* hash del file
* data di ultima modifica
* strategia di chunking usata

Queste informazioni vengono salvate nelle metadata di ChromaDB.

Questo è utile perché prima il progetto faceva una chiamata extra al modello solo per estrarre il nome del candidato.

Adesso questa chiamata non serve più.

## Eliminazione della doppia chiamata al modello

Prima il flusso era questo:

```text
utente fa una domanda
il sistema cerca in ChromaDB
il sistema legge le prime righe del CV
il sistema chiama il modello per estrarre il nome
il sistema chiama di nuovo il modello per generare la risposta
```

Quindi c'erano due chiamate al modello.

Adesso il flusso è questo:

```text
utente fa una domanda
il sistema cerca in ChromaDB
il sistema legge nome, email e telefono dalle metadata
il sistema chiama il modello una sola volta per generare la risposta
```

Questo rende il progetto più veloce e più ordinato.

## chunking.py

Questo file contiene tutta la logica del chunking.

Il chunking è la divisione del testo in parti più piccole.

È importante perché un CV intero può essere troppo lungo o poco preciso per una ricerca vettoriale.

Se i chunk sono fatti bene, il sistema recupera informazioni più precise.

## Strategie di chunking

Nel progetto ci sono più strategie di chunking.

### SectionChunker

Divide il testo usando il separatore:

```text
###
```

È utile quando i CV sono già ben strutturati.

Esempio:

```text
### Esperienza
### Competenze
### Formazione
```

### ParagraphChunker

Divide il testo per paragrafi.

È utile quando il CV è scritto in blocchi separati da righe vuote.

### FixedSizeChunker

Divide il testo in blocchi di dimensione fissa.

È semplice, ma può tagliare il testo in punti poco naturali.

### SemanticChunker

È il chunking più intelligente.

Divide il testo cercando i punti in cui cambia il significato.

## Chunking semantico

Il chunking semantico è stato ispirato dal codice visto a lezione.

La logica è questa:

1. Divido il testo in frasi.
2. Per ogni frase creo una frase combinata con un po' di contesto prima e dopo.
3. Calcolo gli embedding delle frasi combinate.
4. Calcolo la distanza semantica tra frasi consecutive.
5. Trovo i punti in cui la distanza è alta.
6. Uso quei punti per creare i chunk.

In pratica, il sistema cerca di capire dove cambia l'argomento.

Esempio:

```text
Ha esperienza in Python e API REST.
Ha lavorato con Docker e PostgreSQL.
Parla inglese e spagnolo.
```

Le prime due frasi parlano di competenze tecniche.

La terza frase parla di lingue.

Il chunking semantico può decidere di separare questi due argomenti.

## Buffer nel chunking semantico

Il parametro:

```python
SEMANTIC_BUFFER_SIZE = 1
```

significa che ogni frase viene analizzata insieme alla frase precedente e alla frase successiva.

Questo aiuta il modello a capire meglio il contesto.

Se il buffer fosse zero, ogni frase sarebbe analizzata da sola.

## Percentile nel chunking semantico

Il parametro:

```python
SEMANTIC_BREAKPOINT_PERCENTILE = 90
```

serve a decidere quando tagliare.

Il sistema calcola tante distanze tra frasi vicine.

Poi prende solo le distanze più alte.

Se il percentile è alto, il sistema taglia meno.

Se il percentile è basso, il sistema taglia più spesso.

Esempi:

```python
SEMANTIC_BREAKPOINT_PERCENTILE = 95
```

Taglia solo quando il cambio di significato è molto forte.

```python
SEMANTIC_BREAKPOINT_PERCENTILE = 85
```

Taglia più spesso.

## Dimensione minima dei chunk

Il parametro:

```python
SEMANTIC_MIN_CHUNK_SIZE = 250
```

serve a evitare chunk troppo piccoli.

Un chunk troppo piccolo può essere poco utile perché contiene poco contesto.

## Refactoring del chunking

All'inizio il chunking era dentro `document_processor.py`.

Questo rendeva il file troppo grande.

Il refactoring ha separato le responsabilità.

Adesso:

```text
document_processor.py
```

si occupa dei documenti.

```text
chunking.py
```

si occupa solo del chunking.

Questa separazione rende il progetto più facile da capire e da modificare.

Se in futuro voglio aggiungere una nuova strategia di chunking, posso creare una nuova classe dentro `chunking.py`.

## ChunkerFactory

Nel file `chunking.py` c'è anche una factory.

La factory serve a scegliere automaticamente quale chunker usare.

Esempio:

```python
class ChunkerFactory:
    @staticmethod
    def create():
        strategy = Config.CHUNKING_STRATEGY

        if strategy == "section":
            return SectionChunker()

        if strategy == "paragraph":
            return ParagraphChunker()

        if strategy == "fixed":
            return FixedSizeChunker()

        if strategy == "semantic":
            return SemanticChunker()

        return SectionChunker()
```

In questo modo, nel resto del progetto posso scrivere solo:

```python
chunker = ChunkerFactory.create()
chunks = chunker.split(text)
```

Il resto del codice non deve sapere quale strategia è attiva.

## __init__.py

Questo è il file principale dell'app Chainlit.

Qui vengono gestiti:

* avvio della chat
* messaggi dell'utente
* ricerca in ChromaDB
* chiamata al modello LLM
* streaming della risposta
* pulsanti Action di Chainlit

## Azioni Chainlit

Nel progetto ho aggiunto alcuni pulsanti per sfruttare meglio Chainlit.

I pulsanti sono:

* Sincronizza CV
* Statistiche indice
* Carica CV
* Reset indice

## Pulsante Sincronizza CV

Questo pulsante richiama:

```python
DocumentProcessor.process_documents(db)
```

Serve per aggiornare ChromaDB in base ai file presenti nella cartella `resumes`.

Se aggiungo, modifico o cancello un CV, posso cliccare questo pulsante.

## Pulsante Statistiche indice

Questo pulsante mostra informazioni utili sul database.

Mostra:

* numero di file indicizzati
* numero totale di chunk
* cartella dei documenti
* strategia di chunking
* nome, email e telefono dei candidati quando disponibili
* hash breve dei file

È utile per controllare se il progetto sta funzionando bene.

## Pulsante Carica CV

Questo pulsante permette di caricare un file `.txt` direttamente dall'interfaccia Chainlit.

Il file viene copiato nella cartella:

```text
resumes
```

Poi parte subito la sincronizzazione.

Così non devo riavviare il progetto.

## Pulsante Reset indice

Questo pulsante svuota ChromaDB.

Prima di cancellare, il sistema chiede conferma.

Il reset elimina i chunk indicizzati, ma non elimina i file nella cartella `resumes`.

Dopo il reset posso cliccare “Sincronizza CV” per reindicizzare tutto.

## utils.py

Questo file contiene la logica per comunicare con il modello LLM.

Nel progetto uso `AsyncOpenAI`.

Questo permette di usare sia Ollama locale sia OpenAI cloud con una struttura simile.

Le funzioni principali sono:

```python
LLMHelper.chat()
```

Esegue la chiamata al modello e restituisce lo stream.

```python
LLMHelper.create_prompt()
```

Costruisce il prompt finale usando la domanda dell'utente e il contesto recuperato da ChromaDB.

La vecchia funzione:

```python
LLMHelper.get_candidate_name()
```

non è più necessaria nel flusso principale, perché il nome viene estratto durante l'indicizzazione.

## Come funziona il flusso completo

Il flusso del progetto è questo:

```text
1. Metto i CV in resumes
2. Avvio Chainlit
3. Il sistema sincronizza i CV con ChromaDB
4. Ogni CV viene letto
5. Il testo viene diviso in chunk
6. I chunk vengono trasformati in embedding
7. Gli embedding vengono salvati in ChromaDB
8. L'utente fa una domanda
9. ChromaDB trova il chunk più simile alla domanda
10. Il sistema prende metadata e testo del chunk
11. Il prompt viene creato
12. Il modello LLM genera la risposta
13. Chainlit mostra la risposta in streaming
```

## Installazione

Per installare il progetto:

```bash
poetry install
```

Se servono le dipendenze per il chunking semantico:

```bash
poetry add numpy scikit-learn langchain-openai
```

## Variabili ambiente

Serve una chiave OpenAI per gli embedding.

Creo un file `.env` oppure imposto la variabile ambiente:

```bash
export OPENAI_API_KEY="la_tua_chiave"
```

Il file `.env` non deve essere caricato su GitHub.

## Avvio con Chainlit

Per avviare il progetto:

```bash
poetry run chainlit run src/hr_assistant/__init__.py -w
```

Il parametro `-w` serve per ricaricare l'app quando modifico il codice.

## Test della sincronizzazione

Per testare solo la sincronizzazione senza Chainlit, uso:

```bash
poetry run python test_sync.py
```

Il file `test_sync.py` può contenere:

```python
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
```

## Test consigliati

### Test file nuovo

Aggiungo un nuovo file `.txt` in `resumes`.

Poi lancio:

```bash
poetry run python test_sync.py
```

Mi aspetto:

```text
added: 1
```

### Test file invariato

Rilancio subito il test senza modificare nulla.

Mi aspetto:

```text
unchanged: numero_totale_cv
```

### Test file modificato

Modifico un CV.

Poi rilancio il test.

Mi aspetto:

```text
updated: 1
```

### Test file eliminato

Cancello un CV dalla cartella `resumes`.

Poi rilancio il test.

Mi aspetto:

```text
removed: 1
```

## Come provare il chunking

Nel file `config.py` posso cambiare:

```python
CHUNKING_STRATEGY = "semantic"
```

Con questi valori:

```python
CHUNKING_STRATEGY = "section"
```

```python
CHUNKING_STRATEGY = "paragraph"
```

```python
CHUNKING_STRATEGY = "fixed"
```

```python
CHUNKING_STRATEGY = "semantic"
```

Quando cambio strategia, la `chunking_signature` cambia.

Quindi il sistema capisce che deve reindicizzare i CV.

## Domande utili per testare il RAG

Esempi di domande:

```text
Chi è il candidato migliore per un ruolo da software engineer?
```

```text
Cerco una persona con esperienza in sicurezza informatica.
```

```text
Chi ha esperienza in automazione dei processi operativi?
```

```text
Quale candidato è più adatto per un ruolo ibrido tra operations e automazione?
```

```text
Chi ha esperienza nella gestione di team?
```

## File ignorati da Git

Nel `.gitignore` ho escluso:

```text
.env
.vscode
data/
```

Questo serve perché:

* `.env` contiene dati sensibili
* `.vscode` contiene configurazioni locali
* `data/` contiene il database ChromaDB, che può diventare pesante

## Cosa ho imparato

Con questo progetto ho lavorato su diversi concetti importanti:

* struttura di un progetto Python con Poetry
* uso di Chainlit per creare una chat
* uso di ChromaDB come database vettoriale
* differenza tra modello embedding e modello LLM
* persistenza dei dati su disco
* sincronizzazione incrementale dei documenti
* metadata nei documenti
* chunking dei testi
* chunking semantico
* refactoring del codice
* streaming delle risposte
* uso di pulsanti Action in Chainlit

## Possibili miglioramenti futuri

Alcune funzionalità che potrei aggiungere sono:

* ranking dei candidati rispetto a una job description
* esportazione dei risultati in CSV o JSON
* gestione di PDF e DOCX oltre ai file `.txt`
* confronto tra più candidati nella stessa risposta
* punteggio di compatibilità candidato ruolo
* dashboard più completa in Chainlit
* test automatici con pytest
* deploy del progetto con Docker

## Riassunto finale

Questo progetto è partito come un semplice assistente HR basato su CV in `.txt`.

Poi è stato migliorato passo dopo passo.

Prima ho aggiunto la persistenza con ChromaDB.

Poi ho aggiunto la sincronizzazione intelligente dei file.

Dopo ho inserito i pulsanti Chainlit per gestire il progetto dalla UI.

Poi ho eliminato una chiamata inutile al modello, salvando nome, email e telefono nelle metadata.

Infine ho aggiunto il chunking semantico e ho fatto un refactoring per separare meglio il codice.

Adesso il progetto è più ordinato, più efficiente e più facile da spiegare.
