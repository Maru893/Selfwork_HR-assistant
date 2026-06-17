# HR Assistant

Questo progetto si chiama `hr-assistant`.

È un assistente HR sviluppato in Python 3.12 con Poetry. Il suo scopo è aiutare a cercare candidati dentro una raccolta di CV e documenti.

All'inizio il progetto lavorava solo con file `.txt`. Poi è stato migliorato passo dopo passo fino a gestire anche altri formati, come PDF, Word, PowerPoint, Excel, CSV, JSON, XML, HTML e ZIP.

Il progetto usa un approccio RAG, cioè Retrieval Augmented Generation. In parole semplici, prima cerca le parti più utili nei documenti e poi usa un modello di linguaggio per generare una risposta più chiara.

L'interfaccia è fatta con Chainlit, quindi posso usare il progetto come una chat.



## Tecnologie usate

Le tecnologie principali sono:

* Python 3.12
* Poetry, per gestire il progetto e le dipendenze
* Chainlit, per creare l'interfaccia chat
* ChromaDB, per salvare e cercare i vettori
* OpenAI embeddings, per trasformare i testi in vettori
* Ollama, per usare un modello locale come Llama 3.2
* OpenAI, come alternativa cloud per il completamento
* Scikit learn, per calcolare la similarità coseno
* NumPy, per calcolare il percentile nel chunking semantico
* MarkItDown, per convertire file diversi in testo Markdown

## Struttura del progetto

```text
hr-assistant/
├── pyproject.toml
├── poetry.lock
├── README.md
├── .gitignore
├── .chainlit/
│   └── config.toml
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

## config.py

Questo file contiene le impostazioni principali del progetto.

Qui vengono configurati:

* la cartella dei documenti
* il nome della collection ChromaDB
* la cartella di persistenza di ChromaDB
* il modello embedding
* la chiave OpenAI
* il modello LLM
* l'URL delle API
* la strategia di chunking
* i parametri del chunking semantico
* la versione del processor

Esempio:

```python
class Config:
    DOCUMENTS_DIR = "resumes"
    COLLECTION_NAME = "CVs"
    PERSISTENT_DIR = "data/chromadb"

    PROCESSOR_VERSION = "fase7_multiformat_v1"

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

Il modello embedding serve a trasformare i documenti in vettori.

Il modello LLM serve a generare le risposte nella chat.

La variabile `PROCESSOR_VERSION` serve per indicare che è cambiato il modo di processare i documenti. Se questa versione cambia, il sistema può capire che deve reindicizzare i file.

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

Quindi, quando riavvio il progetto, non devo ricaricare tutti i documenti da zero.

Le funzioni principali sono:

* `add_documents()`, aggiunge i chunk dentro ChromaDB
* `query()`, cerca i chunk più simili alla domanda dell'utente
* `get_tracked_files()`, legge i file già indicizzati
* `remove_document_by_source()`, rimuove da ChromaDB tutti i chunk di un file specifico
* `count()`, conta quanti chunk sono presenti nel database
* `reset()`, svuota la collection e la ricrea

## document_processor.py

Questo file si occupa dei documenti.

Il suo compito è:

* controllare quali file sono supportati
* leggere o convertire i file
* calcolare l'hash del file
* estrarre metadata utili
* dividere il testo in chunk
* sincronizzare la cartella `resumes` con ChromaDB

Prima il progetto caricava i documenti solo se il database era vuoto.

Adesso invece fa un confronto intelligente tra la cartella `resumes` e quello che è già salvato in ChromaDB.

## Formati supportati, FASE 7

Con la FASE 7 il progetto non lavora più solo con file `.txt`.

I formati supportati sono:

```text
.txt
.pdf
.doc
.docx
.ppt
.pptx
.xls
.xlsx
.html
.htm
.csv
.json
.xml
.zip
```

Nel codice questi formati sono definiti dentro `DocumentProcessor`:

```python
SUPPORTED_EXTENSIONS = {
    ".txt": "text",
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
    ".ppt": "presentation",
    ".pptx": "presentation",
    ".xls": "spreadsheet",
    ".xlsx": "spreadsheet",
    ".html": "web",
    ".htm": "web",
    ".csv": "data",
    ".json": "data",
    ".xml": "data",
    ".zip": "archive",
}
```

Ogni estensione ha anche un tipo logico, per esempio `document`, `presentation`, `spreadsheet`, `data` o `archive`.

## Conversione dei documenti con MarkItDown

I file come PDF, DOCX, PPTX e XLSX non si possono leggere bene con un semplice `open()`.

Per questo uso MarkItDown.

Il flusso è questo:

```text
file originale
conversione con MarkItDown
testo Markdown
chunking semantico
embedding
salvataggio in ChromaDB
```

Per i file `.txt`, il progetto legge direttamente il contenuto.

Per gli altri formati, prova a convertirli in Markdown.

Se la conversione fallisce per formati testuali come CSV, JSON, XML o HTML, il sistema prova comunque a leggerli come testo.

## Gestione dei file ZIP

Il progetto supporta anche i file `.zip`.

Quando trova uno ZIP:

1. crea una cartella temporanea
2. estrae i file interni
3. controlla quali file interni sono supportati
4. converte ogni file interno in Markdown
5. unisce i contenuti
6. indicizza lo ZIP come un documento unico

Nelle metadata viene salvato anche:

```text
internal_files_count
```

Questo valore indica quanti file interni sono stati letti dallo ZIP.

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

Questo permette al sistema di capire quali documenti devono essere aggiornati.

## Metadata dei documenti

Durante l'indicizzazione, il progetto salva alcune informazioni nelle metadata di ChromaDB.

Le metadata principali sono:

* nome del candidato
* email
* numero di telefono
* nome del file
* hash del file
* data di ultima modifica
* strategia di chunking usata
* tipo file
* estensione
* MIME type
* numero di file interni se il file è uno ZIP

Queste informazioni sono utili perché posso mostrarle nelle statistiche e posso usarle nella risposta finale.

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

È importante perché un documento intero può essere troppo lungo o poco preciso per una ricerca vettoriale.

Se i chunk sono fatti bene, il sistema recupera informazioni più precise.

## Strategie di chunking

Nel progetto ci sono più strategie di chunking.

### SectionChunker

Divide il testo usando il separatore:

```text
###
```

È utile quando i documenti sono già ben strutturati.

### ParagraphChunker

Divide il testo per paragrafi.

È utile quando il documento è scritto in blocchi separati da righe vuote.

### FixedSizeChunker

Divide il testo in blocchi di dimensione fissa.

È semplice, ma può tagliare il testo in punti poco naturali.

### SemanticChunker

È il chunking più intelligente.

Divide il testo cercando i punti in cui cambia il significato.

## Chunking semantico

Il chunking semantico è stato ispirato dal codice visto a lezione.

La logica è questa:

1. divido il testo in frasi
2. per ogni frase creo una frase combinata con un po' di contesto prima e dopo
3. calcolo gli embedding delle frasi combinate
4. calcolo la distanza semantica tra frasi consecutive
5. trovo i punti in cui la distanza è alta
6. uso quei punti per creare i chunk

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

## Parametri del chunking semantico

Il parametro:

```python
SEMANTIC_BUFFER_SIZE = 1
```

significa che ogni frase viene analizzata insieme alla frase precedente e alla frase successiva.

Il parametro:

```python
SEMANTIC_BREAKPOINT_PERCENTILE = 90
```

serve a decidere quando tagliare.

Se il percentile è alto, il sistema taglia meno.

Se il percentile è basso, il sistema taglia più spesso.

Il parametro:

```python
SEMANTIC_MIN_CHUNK_SIZE = 250
```

serve a evitare chunk troppo piccoli.

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
* caricamento documenti dall'interfaccia

## Azioni Chainlit

Nel progetto ho aggiunto alcuni pulsanti per sfruttare meglio Chainlit.

I pulsanti sono:

* Sincronizza CV
* Statistiche indice
* Carica documenti
* Reset indice

## Pulsante Sincronizza CV

Questo pulsante richiama:

```python
DocumentProcessor.process_documents(db)
```

Serve per aggiornare ChromaDB in base ai file presenti nella cartella `resumes`.

Se aggiungo, modifico o cancello un documento, posso cliccare questo pulsante.

## Pulsante Statistiche indice

Questo pulsante mostra informazioni utili sul database.

Mostra:

* numero di file indicizzati
* numero totale di chunk
* cartella dei documenti
* strategia di chunking
* nome, email e telefono dei candidati quando disponibili
* estensione del file
* tipo del file
* hash breve dei file

È utile per controllare se il progetto sta funzionando bene.

## Pulsante Carica documenti, FASE 8

Questo pulsante permette di caricare documenti direttamente dall'interfaccia Chainlit.

I file caricati vengono copiati nella cartella:

```text
resumes
```

Poi parte subito la sincronizzazione.

Così non devo riavviare il progetto.

I formati caricabili sono gli stessi supportati dal backend.

## Upload diretto nella chat

Oltre al pulsante, ho abilitato anche il caricamento diretto nella chat.

Questo significa che posso trascinare un file nel messaggio oppure allegarlo.

Nel codice, Chainlit passa questi file dentro:

```python
message.elements
```

Se il messaggio contiene file, il sistema li salva in `resumes`, li sincronizza e poi si ferma.

Uso `return` dopo il caricamento perché non voglio che il sistema interpreti il caricamento come una domanda HR.

## Cartella .files

Durante i test ho visto che Chainlit usa una cartella temporanea chiamata:

```text
.files
```

Questa cartella serve per gestire i file caricati.

Se non esiste, Chainlit può dare un errore durante l'upload.

Per evitare il problema, nel codice creo la cartella con:

```python
os.makedirs(".files", exist_ok=True)
```

La cartella `.files` non deve essere caricata su GitHub, quindi va messa nel `.gitignore`.

## Configurazione Chainlit per upload diretto

Nel file:

```text
.chainlit/config.toml
```

ho abilitato il caricamento spontaneo dei file.

La sezione è simile a questa:

```toml
[features.spontaneous_file_upload]
    enabled = true
    accept = [
        "text/plain",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/html",
        "text/csv",
        "application/json",
        "application/xml",
        "text/xml",
        "application/zip"
    ]
    max_files = 10
    max_size_mb = 20
```

Durante la configurazione ho avuto un errore TOML perché avevo due volte la chiave `accept`.

Il problema era che nel file c'era ancora:

```toml
accept = ["*/*"]
```

L'ho eliminata e ho lasciato una sola configurazione `accept`.

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

* `LLMHelper.chat()`, esegue la chiamata al modello e restituisce lo stream
* `LLMHelper.create_prompt()`, costruisce il prompt finale usando la domanda dell'utente e il contesto recuperato da ChromaDB

La vecchia funzione:

```python
LLMHelper.get_candidate_name()
```

non è più necessaria nel flusso principale, perché il nome viene estratto durante l'indicizzazione.

## Come funziona il flusso completo

Il flusso del progetto ora è questo:

```text
1. Metto i documenti in resumes oppure li carico da Chainlit
2. Il sistema salva i file nella cartella resumes
3. Il sistema sincronizza resumes con ChromaDB
4. Ogni documento viene convertito in Markdown se serve
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

## Creazione e installazione del progetto con Poetry

Questa sezione spiega come creare e avviare il progetto usando Poetry.

Poetry serve a gestire:

* la struttura del progetto Python
* le dipendenze
* il file `pyproject.toml`
* l'ambiente virtuale

### Creare un nuovo progetto con Poetry

Per creare un progetto da zero:

```bash
poetry new nome_progetto
cd nome_progetto
```

Nel caso di questo progetto, il nome è:

```bash
hr-assistant
```

Quindi la cartella del progetto è:

```bash
cd hr-assistant
```

### Installare le dipendenze del progetto

Se il progetto esiste già e contiene il file `pyproject.toml`, basta lanciare:

```bash
poetry install
```

Questo comando legge il file `pyproject.toml` e installa tutte le dipendenze necessarie.

### Aggiungere le dipendenze principali

Per aggiungere le librerie principali usate nel progetto:

```bash
poetry add chromadb openai chainlit numpy scikit-learn langchain-openai
```

Queste dipendenze servono per:

* `chromadb`, database vettoriale
* `openai`, embeddings e chiamate API compatibili
* `chainlit`, interfaccia chat
* `numpy`, calcoli numerici
* `scikit-learn`, similarità coseno
* `langchain-openai`, supporto agli embeddings nel chunking semantico

### Aggiungere il supporto per file diversi

Per leggere e convertire formati come PDF, Word, PowerPoint, Excel, CSV, JSON, XML e ZIP, uso MarkItDown.

Installazione base:

```bash
poetry add markitdown
```

Oppure, se voglio installare anche le dipendenze opzionali:

```bash
poetry add "markitdown[all]"
```

### Configurare la chiave OpenAI

Il progetto usa gli embeddings OpenAI, quindi serve una chiave API.

Creo un file `.env` nella root del progetto:

```bash
touch .env
```

Dentro `.env` inserisco:

```text
OPENAI_API_KEY="la_tua_chiave_openai"
```

Il file `.env` non deve essere caricato su GitHub.

### Errore di versioni Python o librerie

Se durante l'installazione compare un errore legato alla versione di Python o alla compatibilità delle librerie, controllo il file:

```text
pyproject.toml
```

Nella sezione `[project]` posso trovare una riga simile a questa:

```toml
requires-python = ">=3.12,<4.0.0"
```

Questa riga indica quali versioni di Python sono compatibili con il progetto.

Se sto usando Python 3.13, posso impostare:

```toml
requires-python = ">=3.13,<4.0.0"
```

Se invece sto usando Python 3.12, devo lasciare:

```toml
requires-python = ">=3.12,<4.0.0"
```

Dopo la modifica, posso controllare quale versione di Python usa Poetry con:

```bash
poetry env info
```

Se voglio forzare Poetry a usare Python 3.13, posso eseguire:

```bash
poetry env use python3.13
```

Se voglio forzare Poetry a usare Python 3.12, posso eseguire:

```bash
poetry env use python3.12
```

Poi reinstallo le dipendenze:

```bash
poetry install
```

### Ambiente virtuale con Poetry

Poetry crea e gestisce automaticamente un ambiente virtuale.

Nella maggior parte dei casi non serve attivarlo manualmente, perché posso eseguire i comandi con:

```bash
poetry run comando
```

Esempio:

```bash
poetry run python test_sync.py
```

Se invece voglio attivare manualmente l'ambiente virtuale, posso usare:

```bash
eval $(poetry env activate)
```

Dopo l'attivazione posso usare direttamente:

```bash
python test_sync.py
```

Per vedere il percorso dell'ambiente virtuale:

```bash
poetry env info --path
```

### Avviare il progetto con Chainlit

Per avviare l'interfaccia chat:

```bash
poetry run chainlit run src/hr_assistant/__init__.py -w
```

Il parametro `-w` serve per ricaricare automaticamente l'app quando modifico il codice.

Dopo l'avvio, Chainlit apre l'app su:

```text
http://localhost:8000
```



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

Aggiungo un nuovo file supportato in `resumes`.

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
unchanged: numero_totale_documenti
```

### Test file modificato

Modifico un documento.

Poi rilancio il test.

Mi aspetto:

```text
updated: 1
```

### Test file eliminato

Cancello un documento dalla cartella `resumes`.

Poi rilancio il test.

Mi aspetto:

```text
removed: 1
```

### Test upload da Chainlit

Avvio Chainlit:

```bash
poetry run chainlit run src/hr_assistant/__init__.py -w
```

Poi clicco “Carica documenti” e provo a caricare:

```text
.txt
.pdf
.csv
.json
.docx
.zip
```

Dopo il caricamento controllo il report e poi clicco “Statistiche indice”.

### Test RAG dopo upload

Dopo aver caricato un documento, faccio una domanda legata al suo contenuto.

Esempi:

```text
Chi ha competenze in Power BI?
```

```text
Chi ha esperienza in pianificazione e budget?
```

```text
Quale documento parla di cybersecurity?
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

Quindi il sistema capisce che deve reindicizzare i documenti.

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

```text
Chi ha competenze in Power BI?
```

```text
Quale documento parla di pianificazione e budget?
```


## Personalizzazione grafica, FASE finale

Nella fase finale ho personalizzato l'interfaccia grafica di Chainlit.

L'obiettivo non era solo copiare il tema visto a lezione, ma dare al progetto un'identità più personale e più professionale.

La personalizzazione riguarda:

* nome dell'app
* tema chiaro e tema scuro
* colori principali
* stile dell'input della chat
* stile dei pulsanti
* logo o immagine principale
* avatar dell'assistente
* pagina iniziale `chainlit.md`
* file statici dentro la cartella `public`

## File usati per la personalizzazione grafica

I file principali sono:

```text
.chainlit/config.toml
public/app.css
public/theme.json
public/avatars/
chainlit.md
```

Nel file `.chainlit/config.toml` configuro la parte UI di Chainlit.

Esempio:

```toml
[UI]
name = "HR Assistant"
default_theme = "light"
language = "it-IT"
description = "Assistente HR per cercare candidati e analizzare CV con RAG."
cot = "hidden"
custom_css = "/public/app.css"
alert_style = "modern"
default_avatar_file_url = "/public/avatars/system_assistant.png"
custom_meta_image_url = "/public/avatars/hr_assistant.png"
```

Ho lasciato `cot = "hidden"` perché nella versione finale l'interfaccia deve essere più pulita e adatta a un utilizzo normale.

## Scelta dello stile grafico

Per la versione finale voglio usare uno stile più professionale rispetto al tema di partenza.

La direzione scelta è:

```text
professionale
pulita
moderna
leggibile
adatta a un progetto HR e RAG
```

I colori principali sono:

* blu scuro, per dare un'idea aziendale e professionale
* verde acqua, per dare un tocco moderno e tecnologico
* grigio chiaro, per mantenere l'interfaccia leggibile
* sfondo scuro bilanciato nella modalità dark

Il file `theme.json` contiene le variabili del tema.

Il file `app.css` contiene alcune regole CSS per migliorare l'aspetto dell'interfaccia, per esempio:

* input più arrotondato
* sfondo più morbido
* messaggi più leggibili
* pulsanti più moderni
* bordi più coerenti

## Pagina iniziale Chainlit

Il file `chainlit.md` contiene il testo mostrato nella sezione “Leggimi”.

La pagina iniziale spiega:

* cos'è HR Assistant
* cosa può fare l'utente
* quali formati sono supportati
* come funziona il sistema RAG in modo semplice

## Test della personalizzazione grafica

Per testare la grafica avvio Chainlit:

```bash
poetry run chainlit run src/hr_assistant/__init__.py -w
```

Poi controllo:

* tema chiaro
* tema scuro
* pulsanti
* input della chat
* pagina “Leggimi”
* caricamento documenti
* avatar dell'assistente
* leggibilità delle risposte




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
* gestione di formati diversi con MarkItDown
* caricamento documenti dall'interfaccia
* configurazione di upload file in Chainlit
* gestione di file temporanei con `.files`
* personalizzazione grafica di Chainlit
* uso di `theme.json`
* uso di CSS custom con `public/app.css`
* gestione di logo, avatar e pagina iniziale



## Riassunto finale

Questo progetto è partito come un semplice assistente HR basato su CV in `.txt`.

Poi è stato migliorato passo dopo passo.

Prima ho aggiunto la persistenza con ChromaDB.

Poi ho aggiunto la sincronizzazione intelligente dei file.

Dopo ho inserito i pulsanti Chainlit per gestire il progetto dalla UI.

Poi ho eliminato una chiamata inutile al modello, salvando nome, email e telefono nelle metadata.

Poi ho aggiunto il chunking semantico e ho fatto un refactoring per separare meglio il codice.

Con la FASE 7 ho aggiunto la gestione di file diversi usando MarkItDown.

Con la FASE 8 ho aggiunto il caricamento dei documenti direttamente da Chainlit.

Nella fase finale ho personalizzato l'interfaccia grafica di Chainlit con un tema più professionale, colori più coerenti, CSS custom, avatar e una pagina iniziale dedicata.
