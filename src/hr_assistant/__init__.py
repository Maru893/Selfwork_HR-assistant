import os
import chainlit as cl
from hr_assistant.document_processor import DocumentProcessor
from hr_assistant.database import Database
from hr_assistant.config import Config
from hr_assistant.utils import LLMHelper

# Inizializza il database persistente
db = Database()

# FASE 3: Ottimizzazione dell'efficienza. Aggiunge i documenti SOLO se il DB è vuoto
if db.count() == 0:
    documents, metadatas, ids = DocumentProcessor.process_documents()
    if documents:
        db.add_documents(documents, metadatas, ids)
        print(f" Database vuoto: Inseriti {len(documents)} nuovi chunk nella cartella {Config.PERSISTENT_DIR}.")
    else:
        print(" Database vuoto e nessun file .txt rilevato nella cartella resumes.")
else:
    print(f" Database rilevato su disco: Caricati {db.count()} vettori esistenti (Nessun ricaricamento necessario).")


@cl.on_chat_start
async def start():
    cl.user_session.set(
        "messages",
        [
            {
                "role": "system",
                "content": """
                    Sei un assistente specializzato nel mondo HR, rispondi in modo professionale, sintetico e pragmatico.
                    Il tuo ruolo è dynamic_map individuare il candidato ideale rispetto alle richieste dell'utente.
                """,
            }
        ],
    )
    await cl.Message(content="🎯 **HR Assistant Pronto (Struttura a moduli e Persistenza FASE 3 Attiva).** Chiedimi pure!").send()


@cl.on_message
async def handle_message(message: cl.Message):
    user_question = message.content
    
    if db.count() == 0:
        await cl.Message(content="⚠️ Il database dei CV è vuoto. Inserisci dei file .txt in `resumes` per iniziare.").send()
        return

    results = db.query(user_question)

    filename = results["metadatas"][0][0]["source"]
    context_lines = DocumentProcessor.read_first_lines(
        os.path.join(Config.DOCUMENTS_DIR, filename), 10
    )

    context = f"CONTESTO: nome file {results['metadatas'][0][0]['source']} ecco il paragrafo piu' significativo: {results['documents'][0][0]}"

    candidate_name = await LLMHelper.get_candidate_name(context_lines)

    prompt = LLMHelper.create_prompt(context, user_question, candidate_name)

    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    response_message = cl.Message(content="")
    await response_message.send()

    try:
        # FASE 3: Chiamata stream asincrona corretta
        stream = await LLMHelper.chat(messages)

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                await response_message.stream_token(str(content))

        messages.append({"role": "assistant", "content": response_message.content})
        await response_message.update()

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await cl.Message(content=error_message).send()
        print(error_message)

    cl.user_session.set("messages", messages)

@cl.on_chat_end
async def end():
    await cl.Message(content="Grazie per aver utilizzato il nostro assistente. Buona giornata!").send()
