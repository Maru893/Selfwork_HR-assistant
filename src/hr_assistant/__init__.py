import os
import asyncio
import shutil
from pathlib import Path

import chainlit as cl

from hr_assistant.document_processor import DocumentProcessor
from hr_assistant.database import Database
from hr_assistant.config import Config
from hr_assistant.utils import LLMHelper


db = Database()

ACCEPTED_UPLOAD_TYPES = {
    "text/plain": [".txt"],
    "application/pdf": [".pdf"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/vnd.ms-powerpoint": [".ppt"],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
    "application/vnd.ms-excel": [".xls"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    "text/html": [".html", ".htm"],
    "text/csv": [".csv"],
    "application/json": [".json"],
    "application/xml": [".xml"],
    "text/xml": [".xml"],
    "application/zip": [".zip"],
}

def is_supported_upload(file_name: str) -> bool:
    extension = Path(file_name).suffix.lower()
    return extension in DocumentProcessor.SUPPORTED_EXTENSIONS


def save_uploaded_file(uploaded_file) -> str:
    os.makedirs(Config.DOCUMENTS_DIR, exist_ok=True)

    safe_file_name = Path(uploaded_file.name).name
    destination = Path(Config.DOCUMENTS_DIR) / safe_file_name

    shutil.copyfile(uploaded_file.path, destination)

    return safe_file_name


async def save_uploaded_files(uploaded_files) -> list[str]:
    saved_files = []

    for uploaded_file in uploaded_files:
        if not is_supported_upload(uploaded_file.name):
            continue

        saved_file_name = await asyncio.to_thread(
            save_uploaded_file,
            uploaded_file,
        )

        saved_files.append(saved_file_name)

    return saved_files

def format_sync_report(report):
    lines = [
        "Sincronizzazione completata.",
        "",
        f"File aggiunti: {report['added']}",
        f"File aggiornati: {report['updated']}",
        f"File rimossi: {report['removed']}",
        f"File invariati: {report['unchanged']}",
        f"File presenti nella cartella: {report['total_files']}",
        f"Chunk indicizzati in questa sync: {report['indexed_chunks']}",
        f"Chunk totali in ChromaDB: {db.count()}",
    ]

    if report["added_files"]:
        lines.append("")
        lines.append("File aggiunti:")
        lines.extend(f"• {filename}" for filename in report["added_files"])

    if report["updated_files"]:
        lines.append("")
        lines.append("File aggiornati:")
        lines.extend(f"• {filename}" for filename in report["updated_files"])

    if report["removed_files"]:
        lines.append("")
        lines.append("File rimossi:")
        lines.extend(f"• {filename}" for filename in report["removed_files"])

    return "\n".join(lines)


def format_index_stats():
    tracked_files = db.get_tracked_files()

    lines = [
        "Statistiche indice",
        "",
        f"File indicizzati: {len(tracked_files)}",
        f"Chunk totali: {db.count()}",
        f"Cartella documenti: {Config.DOCUMENTS_DIR}",
        f"Strategia chunking: {Config.CHUNKING_STRATEGY}",
    ]

    if tracked_files:
        lines.append("")
        lines.append("File tracciati:")

        for filename, metadata in sorted(tracked_files.items()):
            short_hash = metadata["hash"][:10] if metadata.get("hash") else "n.d."
            candidate_name = metadata.get("candidate_name") or "nome non rilevato"
            email = metadata.get("email") or "email non rilevata"
            phone = metadata.get("phone") or "telefono non rilevato"
            extension = metadata.get("extension") or "estensione n.d."
            file_type = metadata.get("file_type") or "tipo n.d."

            lines.append(
                f"• {filename}, {file_type}, {extension}, "
                f"{candidate_name}, {email}, {phone}, hash {short_hash}"
            )

    return "\n".join(lines)


def get_document_actions():
    return [
        cl.Action(
            name="sync_documents",
            label="Sincronizza CV",
            icon="refresh-cw",
            payload={"value": "sync"},
            tooltip="Aggiorna ChromaDB in base alla cartella resumes",
        ),
        cl.Action(
            name="show_index_stats",
            label="Statistiche indice",
            icon="bar-chart-3",
            payload={"value": "stats"},
            tooltip="Mostra file e chunk indicizzati",
        ),
        cl.Action(
            name="upload_documents",
            label="Carica documenti",
            icon="upload",
            payload={"value": "upload"},
            tooltip="Carica CV o documenti supportati",
        ),
        cl.Action(
            name="reset_index",
            label="Reset indice",
            icon="trash-2",
            payload={"value": "reset"},
            tooltip="Svuota la collection ChromaDB",
        ),
    ]


async def send_document_actions():
    await cl.Message(
        content="Gestione documenti",
        actions=get_document_actions(),
    ).send()


@cl.on_chat_start
async def start():
    cl.user_session.set(
        "messages",
        [
            {
                "role": "system",
                "content": """
                    Sei un assistente specializzato nel mondo HR, rispondi in modo professionale, sintetico e pragmatico.
                    Il tuo ruolo è individuare il candidato ideale rispetto alle richieste dell'utente.
                """,
            }
        ],
    )
    os.makedirs(".files", exist_ok=True)
    os.makedirs(Config.DOCUMENTS_DIR, exist_ok=True)

    report = await asyncio.to_thread(
        DocumentProcessor.process_documents,
        db,
    )

    content = (
        "🎯 HR Assistant pronto.\n\n"
        + format_sync_report(report)
        + "\n\n"
        + "Gestione documenti:"
    )

    await cl.Message(
        content=content,
        actions=get_document_actions(),
    ).send()


@cl.action_callback("sync_documents")
async def on_sync_documents(action: cl.Action):
    await action.remove()

    report = await asyncio.to_thread(
        DocumentProcessor.process_documents,
        db,
    )

    await cl.Message(
        content=format_sync_report(report),
    ).send()

    await send_document_actions()


@cl.action_callback("show_index_stats")
async def on_show_index_stats(action: cl.Action):
    await cl.Message(
        content=format_index_stats(),
    ).send()

@cl.action_callback("upload_documents")
async def on_upload_documents(action: cl.Action):
    files = await cl.AskFileMessage(
        content="Carica uno o più documenti supportati.",
        accept=ACCEPTED_UPLOAD_TYPES,
        max_files=10,
        max_size_mb=20,
        timeout=180,
        raise_on_timeout=False,
    ).send()

    if not files:
        await cl.Message(
            content="Nessun file caricato."
        ).send()
        await send_document_actions()
        return

    saved_files = await save_uploaded_files(files)

    if not saved_files:
        await cl.Message(
            content="Nessun file supportato caricato."
        ).send()
        await send_document_actions()
        return

    report = await asyncio.to_thread(
        DocumentProcessor.process_documents,
        db,
    )

    await cl.Message(
        content=(
            "File salvati nella cartella resumes:\n"
            + "\n".join(f"• {file_name}" for file_name in saved_files)
            + "\n\n"
            + format_sync_report(report)
        )
    ).send()

    await send_document_actions()

@cl.action_callback("reset_index")
async def on_reset_index(action: cl.Action):
    response = await cl.AskActionMessage(
        content="Vuoi davvero svuotare l'indice dei CV?",
        actions=[
            cl.Action(
                name="confirm_reset_index",
                label="Conferma reset",
                icon="trash-2",
                payload={"value": "confirm"},
            ),
            cl.Action(
                name="cancel_reset_index",
                label="Annulla",
                icon="x",
                payload={"value": "cancel"},
            ),
        ],
        timeout=60,
        raise_on_timeout=False,
    ).send()

    if not response:
        await cl.Message(
            content="Reset annullato."
        ).send()
        await send_document_actions()
        return

    if response.get("payload", {}).get("value") != "confirm":
        await cl.Message(
            content="Reset annullato."
        ).send()
        await send_document_actions()
        return

    await asyncio.to_thread(db.reset)

    await cl.Message(
        content=(
            "Indice svuotato.\n\n"
            f"Chunk totali in ChromaDB: {db.count()}\n\n"
            "I file nella cartella resumes non sono stati eliminati. "
            "Clicca su Sincronizza CV per reindicizzarli."
        )
    ).send()

    await send_document_actions()   


@cl.on_message
async def handle_message(message: cl.Message):
    if message.elements:
        await cl.Message(
            content="Caricamento e indicizzazione documenti..."
        ).send()

        supported_files = [
            file
            for file in message.elements
            if is_supported_upload(file.name)
        ]

        if not supported_files:
            await cl.Message(
                content="Nessun file supportato trovato nel messaggio."
            ).send()
            await send_document_actions()
            return

        saved_files = await save_uploaded_files(supported_files)

        report = await asyncio.to_thread(
            DocumentProcessor.process_documents,
            db,
        )

        await cl.Message(
            content=(
                "File salvati nella cartella resumes:\n"
                + "\n".join(f"• {file_name}" for file_name in saved_files)
                + "\n\n"
                + format_sync_report(report)
            )
        ).send()

        await send_document_actions()
        return

    user_question = message.content

    if db.count() == 0:
        await cl.Message(
            content="⚠️ Il database dei CV è vuoto. Inserisci dei file .txt in `resumes` per iniziare."
        ).send()
        return

    results = db.query(user_question)

    metadata = results["metadatas"][0][0]
    filename = metadata["source"]

    candidate_name = metadata.get("candidate_name") or "candidato non identificato"
    candidate_email = metadata.get("email") or "email non disponibile"
    candidate_phone = metadata.get("phone") or "telefono non disponibile"

    context = (
        f"CONTESTO:\n"
        f"Nome candidato: {candidate_name}\n"
        f"Email: {candidate_email}\n"
        f"Telefono: {candidate_phone}\n"
        f"Nome file: {filename}\n"
        f"Paragrafo più significativo: {results['documents'][0][0]}"
    )

    prompt = LLMHelper.create_prompt(
        context,
        user_question,
        candidate_name,
    )

    messages = cl.user_session.get("messages", [])
    messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    response_message = cl.Message(content="")
    await response_message.send()

    try:
        stream = await LLMHelper.chat(messages)

        async for chunk in stream:
            content = chunk.choices[0].delta.content

            if content:
                await response_message.stream_token(str(content))

        messages.append(
            {
                "role": "assistant",
                "content": response_message.content,
            }
        )

        await response_message.update()

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await cl.Message(content=error_message).send()
        print(error_message)

    cl.user_session.set("messages", messages)


@cl.on_chat_end
async def end():
    await cl.Message(
        content="Grazie per aver utilizzato il nostro assistente. Buona giornata!"
    ).send()