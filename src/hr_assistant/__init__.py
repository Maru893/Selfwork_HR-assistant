import chainlit as cl
import ollama
import chromadb
import os, uuid
from chromadb.utils import embedding_functions

## FASE 1 - Lettura Files e Chunking
documents_dir = "resumes"

# Creo la cartella resumes se non esiste, così il codice non va in crash al primo avvio
if not os.path.exists(documents_dir):
    os.makedirs(documents_dir)

documents = []
metadatas = []
ids = []

for filename in os.listdir(documents_dir):
    if filename.endswith(".txt"):
        with open(os.path.join(documents_dir, filename), "r", encoding="utf-8") as file:
            chunks = file.read().replace("\n", ".").split("### ")

            for chunk in chunks:
                if not chunk.isspace() and not chunk == "":
                    documents.append(chunk)
                    metadatas.append({"source": filename})
                    guid = str(uuid.uuid4())
                    ids.append(guid)

print(f"Caricati {len(documents)} chunk di testo da analizzare.")

## Fase 2 - Embeddings e inserimento nel DB Vettoriale
# Recupera la chiave in modo sicuro dalle variabili d'ambiente caricate da Chainlit
openai_key = os.getenv("OPENAI_API_KEY")

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=openai_key, model_name="text-embedding-3-small"
)

chroma_client = chromadb.Client()

collection = chroma_client.get_or_create_collection(
    name="CVs", embedding_function=openai_ef
)

# Aggiunge i documenti solo se sono stati effettivamente letti dei file .txt
if documents:
    collection.add(documents=documents, metadatas=metadatas, ids=ids)

## FASE 3 - CHAT VIRTÙALE

# Corretto: Aggiunto 'async' per la gestione nativa di Chainlit
@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set(
        "messages",
        [
            {
                "role": "system",
                "content": "Sei un assistente specializzato nel mondo HR, rispondi in modo professionale, sintetico e pragmatico. Il tuo ruolo è individuare il candidato ideale rispetto alle richieste dell'utente.",
            }
        ],
    )
    # Mandiamo un feedback iniziale all'utente
    await cl.Message(content="**Assistente HR Pronto.** Come posso aiutarti oggi nella ricerca dei candidati?").send()


@cl.on_message
async def handle_message(message: cl.Message):
    user_question = message.content

    # Se non ci sono documenti nel DB, avvisa l'utente ed evita il crash
    if not documents:
        await cl.Message(content="⚠️ Attenzione: Non ho trovato file .txt nella cartella `resumes`. Aggiungi i CV per iniziare.").send()
        return

    results = collection.query(query_texts=[user_question], n_results=1)

    def leggi_prime_100_righe(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            righe = []
            for i, riga in enumerate(file):
                if i < 100:
                    righe.append(riga.strip())
                else:
                    break
        return righe

    filename = results["metadatas"][0][0]["source"]
    context_nome_candidato = leggi_prime_100_righe(
        os.path.join(documents_dir, filename)
    )

    # Estrazione del nome tramite Llama 3.2
    nome_response = ollama.chat(
        model="llama3.2",
        messages=[
            {
                "role": "user",
                "content": f"Dato il seguente contesto individua il nome e cognome del candidato e ritorna solo il nome e cognome del candidato. quello che sto per fornirti e' il curriculum vite del candidato: {context_nome_candidato}",
            }
        ],
    )

    nome = nome_response["message"]["content"].strip()
    context = f"CONTESTO: nome file {results['metadatas'][0][0]['source']} ecco il paragrafo piu' significativo: {results['documents'][0][0]}"

    prompt = f"""
        Dato il seguente contesto: 
        [[[
        {context}
        ]]].
        Rispondi alla domanda dell'utente: [[[ {user_question}]]] .
        Spiega che nel file individuato c'e' il profilo piu' adatto. 
        Assicurati di nominare il Nome dei file.
        Assicurati di indicare il nome del candidato: [[[ {nome} ]]].
        Argometa la scelta utilizzando il contenuto del testo individuato nel contesto.
        Se non trovi corrispondenza in nessun cv non inventare."""

    # Corretto: Sostituito /n con \n per andare a capo correttamente nel terminale
    print("\n\n\n")
    print("*" * 80)
    print(f"Candidato Estratto: {nome}")
    print("*" * 80)
    print(context)
    print("*" * 80)
    print(prompt)
    print("*" * 80)

    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    response_message = cl.Message(content="")
    await response_message.send()

    try:
        stream = ollama.chat(model="llama3.2", messages=messages, stream=True)

        for chunk in stream:
            await response_message.stream_token(chunk["message"]["content"])

        messages.append({"role": "assistant", "content": response_message.content})
        await response_message.update()
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await cl.Message(content=error_message).send()
        print(error_message)

    cl.user_session.set("messages", messages)


# Corretto: Aggiunto 'async' e corretto l'invio asincrono del messaggio finale
@cl.on_chat_end
async def on_chat_end():
    await cl.Message(
        content="Grazie per aver utilizzato il nostro assistente. Buona giornata!"
    ).send()
