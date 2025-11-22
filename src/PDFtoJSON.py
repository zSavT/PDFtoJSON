"""
PDFtoJSON.py

Script per estrarre dati strutturati da file PDF e convertirli in formato JSON
utilizzando l'intelligenza artificiale di Google Gemini.

Funzionalità principali:
- Processa file PDF da una cartella di input.
- Utilizza i modelli generativi di Google (es. Gemini) per analizzare il testo.
- Permette di usare una struttura JSON predefinita (template) per guidare l'estrazione.
- In alternativa, può generare autonomamente una struttura JSON basata sul contenuto del PDF.
- Gestisce la rotazione automatica di più API key per aumentare la resilienza.
"""

import os
import google.generativeai as genai
import json
import argparse
import fitz  # PyMuPDF
import re
from typing import List, Optional, Any


# --- COSTANTI GLOBALI ---
DEFAULT_MODEL_NAME = "gemini-2.5-flash"  # Modello Gemini predefinito.


# --- VARIABILI GLOBALI ---
# Queste variabili mantengono lo stato durante l'esecuzione dello script.

available_api_keys: List[str] = []      # Lista delle API key disponibili, caricate all'avvio.
current_api_key_index: int = 0          # Indice della API key attualmente in uso nella lista `available_api_keys`.
model: Optional[genai.GenerativeModel] = None  # Oggetto del modello Gemini, inizializzato dopo aver configurato l'API key.
current_chat_session: Optional[Any] = None     # Sessione di chat attiva con Gemini. Viene resettata per ogni file.


def get_args_parsed_main_updated() -> argparse.Namespace:
    """
    Configura e analizza gli argomenti della riga di comando.

    Definisce gli argomenti che l'utente può passare allo script, come le cartelle
    di input/output, le API key, il nome del modello e le opzioni per il template JSON.

    Returns:
        argparse.Namespace: Un oggetto contenente gli argomenti analizzati.
    """
    parser = argparse.ArgumentParser(
        description="Script per la conversione di un file PDF in un file JSON tramite AI.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    api_group = parser.add_argument_group('Configurazione API e Modello')
    api_group.add_argument("--api", type=str,
                        help="Specifica una o più chiavi API Google Gemini, separate da virgola.\nAlternativamente, crea un file 'api_key.txt' (una chiave per riga).")
    api_group.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME,
                        help=f"Nome del modello Gemini da utilizzare (es. 'gemini-1.5-pro', '{DEFAULT_MODEL_NAME}').\nDefault: '{DEFAULT_MODEL_NAME}'")
    file_format_group = parser.add_argument_group('Configurazione File Input/Output')
    file_format_group.add_argument("--inputPDF", type=str, default="input",
                        help="Percorso della cartella di input contenente i file PDF.\nDefault: 'input'")
    file_format_group.add_argument("--outputJSON", type=str, default="output",
                        help="Percorso della cartella di output per i file JSON.\nDefault: 'output'")
    file_format_group.add_argument("--json-template", type=str,
                        help="Percorso di un file .txt o .json contenente la struttura JSON da usare come template nel prompt.")
    file_format_group.add_argument("--no-json-template", action='store_true',
                        help="Se attivo, non include la struttura JSON di esempio nel prompt, ma chiede all'AI di crearne una.")
    parsed_args = parser.parse_args()
    return parsed_args


def initialize_api_keys_and_model(args_parsed_main: argparse.Namespace) -> bool:
    """
    Inizializza le API key e il modello generativo di Gemini.

    Carica le API key da due possibili fonti: l'argomento `--api` e il file
    `api_key.txt`. Le chiavi duplicate vengono rimosse.
    Successivamente, tenta di configurare `genai` con la prima chiave disponibile
    e di inizializzare il modello specificato.

    Args:
        args_parsed_main: Gli argomenti parsati dalla riga di comando.

    Returns:
        bool: True se l'inizializzazione ha successo, False altrimenti.
    """
    global available_api_keys, current_api_key_index, model
    print("\n--- Inizializzazione API e Modello ---")
    if args_parsed_main.api:
        keys_from_arg = [key.strip() for key in args_parsed_main.api.split(',') if key.strip()]
        if keys_from_arg:
            available_api_keys.extend(keys_from_arg)
            print(f"{len(keys_from_arg)} API key(s) fornite tramite argomento --api.")

    # Cerca le API key anche in un file di testo per comodità.
    api_key_file_path = "../api_key.txt"
    if os.path.exists(api_key_file_path):
        with open(api_key_file_path, "r") as f:
            keys_from_file = [line.strip() for line in f if line.strip()]
            if keys_from_file:
                available_api_keys.extend(keys_from_file)
                print(f"{len(keys_from_file)} API key(s) caricate da '{api_key_file_path}'.")

    # Rimuove eventuali duplicati per evitare di usare la stessa chiave più volte.
    seen = set()
    available_api_keys = [x for x in available_api_keys if not (x in seen or seen.add(x))]

    if not available_api_keys:
        print("Nessuna API key trovata. Specificare tramite --api o nel file 'api_key.txt'.")
        return False

    print(f"Totale API keys uniche disponibili: {len(available_api_keys)}.")
    current_api_key_index = 0

    try:
        current_key = available_api_keys[current_api_key_index]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(args_parsed_main.model_name)
        print(f"Modello '{args_parsed_main.model_name}' inizializzato con API Key: ...{current_key[-4:]}")
        return True
    except Exception as e:
        print(f"Errore durante l'inizializzazione del modello '{args_parsed_main.model_name}': {e}")
        model = None
        return False
    finally:
        print("-" * 65)

def rotate_api_key(args_parsed_main: argparse.Namespace) -> bool:
    """
    Passa alla API key successiva nella lista.

    Questa funzione viene chiamata quando la chiave corrente fallisce (es. per limiti
    di quota). Se sono disponibili altre chiavi, aggiorna l'indice, riconfigura
    `genai` e reinizializza il modello.

    Args:
        args_parsed_main: Gli argomenti parsati, necessari per reinizializzare il modello.

    Returns:
        bool: True se la rotazione ha successo, False se non ci sono altre chiavi o se la nuova chiave fallisce.
    """
    global current_api_key_index, model
    if len(available_api_keys) <= 1:
        print("Solo una API key disponibile. Impossibile ruotare.")
        return False
    previous_key_index = current_api_key_index
    current_api_key_index = (current_api_key_index + 1) % len(available_api_keys)
    new_api_key = available_api_keys[current_api_key_index]

    print(f"Rotazione API key dalla {previous_key_index+1}° alla {current_api_key_index+1}°...")
    try:
        genai.configure(api_key=new_api_key)
        model = genai.GenerativeModel(args_parsed_main.model_name)
        print(f"API key ruotata e modello '{args_parsed_main.model_name}' riconfigurato.")
        return True
    except Exception as e:
        print(f"ERRORE: Configurazione nuova API Key fallita: {e}")
        # Se la nuova chiave non funziona, si tenta di ripristinare la precedente.
        current_api_key_index = previous_key_index
        try:
            genai.configure(api_key=available_api_keys[previous_key_index])
            model = genai.GenerativeModel(args_parsed_main.model_name)
            print("API Key precedente ripristinata.")
        except Exception as e_revert:
             print(f"Errore nel ripristino della API Key precedente: {e_revert}")
        return False

def start_gemini_chat(initial_prompt: str, max_attempts: int = 3) -> Optional[str]:
    """
    Inizia una nuova sessione di chat con Gemini e invia il prompt iniziale.

    Include una logica di tentativi multipli. Se una richiesta fallisce,
    tenta di ruotare l'API key e riprovare.

    Args:
        initial_prompt: Il prompt da inviare a Gemini per iniziare la conversazione.
        max_attempts: Il numero massimo di tentativi prima di arrendersi.

    Returns:
        Optional[str]: La risposta testuale di Gemini se la richiesta ha successo, altrimenti None.
    """
    global model, current_chat_session
    if model is None:
        print("Errore: Il modello Gemini non è stato inizializzato. Impossibile avviare la chat.")
        return None
    attempt = 0
    while attempt < max_attempts:
        try:
            print(f"\n--- Avvio nuova chat con Gemini (Tentativo {attempt + 1}/{max_attempts}) ---")
            current_chat_session = model.start_chat(history=[])
            response = current_chat_session.send_message(initial_prompt)
            print("Risposta da Gemini ricevuta.")
            return response.text
        except Exception as e:
            print(f"Errore durante la comunicazione con Gemini: {e}")
            # Se ci sono più chiavi e non si è all'ultimo tentativo, si prova a ruotare.
            if len(available_api_keys) > 1 and attempt < max_attempts - 1:
                print("Tentativo di rotazione della API key...")
                if rotate_api_key(get_args_parsed_main_updated()):
                    print("API Key ruotata con successo. Riprovo la chat.")
                else:
                    print("Rotazione API Key fallita. Non posso riprovare.")
                    return None
            else:
                print("Nessun'altra API key disponibile o raggiunto il numero massimo di tentativi.")
                return None
        finally:
            attempt += 1
    return None # Tutti i tentativi sono falliti


def continue_gemini_chat(message: str, args: argparse.Namespace, max_attempts: int = 3) -> Optional[str]:
    """
    Continua una sessione di chat esistente inviando un nuovo messaggio.

    Questa funzione non è attualmente utilizzata nel flusso principale (che usa
    `start_gemini_chat` per ogni file), ma è mantenuta per usi futuri in cui
    potrebbe essere necessaria una conversazione a più turni.
    Include la stessa logica di tentativi e rotazione API di `start_gemini_chat`.

    Args:
        message: Il messaggio da inviare nella chat corrente.
        args: Gli argomenti parsati, necessari per la rotazione della chiave.
        max_attempts: Il numero massimo di tentativi.

    Returns:
        Optional[str]: La risposta testuale di Gemini, o None in caso di fallimento.
    """
    global current_chat_session, model

    if current_chat_session is None:
        print("Errore: Nessuna sessione di chat Gemini attiva. Si prega di avviare una chat per prima cosa.")
        return None
    if model is None:
        print("Errore: Il modello Gemini non è stato inizializzato. Impossibile continuare la chat.")
        return None
    attempt = 0
    while attempt < max_attempts:
        try:
            print(f"\n--- Continuo chat con Gemini (Tentativo {attempt + 1}/{max_attempts}) ---")
            response = current_chat_session.send_message(message)
            print("Risposta da Gemini ricevuta.")
            return response.text
        except Exception as e:
            print(f"Errore durante la comunicazione con Gemini: {e}")
            if len(available_api_keys) > 1 and attempt < max_attempts - 1:
                print("Tentativo di rotazione della API key...")
                if rotate_api_key(get_args_parsed_main_updated()):
                    print("API Key ruotata con successo. Riprovo la chat.")
                    # Dopo la rotazione, il modello viene reinizializzato. È necessario
                    # riavviare la chat, possibilmente ripristinando la cronologia.
                    if current_chat_session and hasattr(current_chat_session, 'history'):
                        temp_history = list(current_chat_session.history)
                        current_chat_session = model.start_chat(history=temp_history)
                        print("Sessione chat ripristinata con la cronologia precedente.")
                    else:
                        current_chat_session = model.start_chat(history=[])
                        print("Sessione chat riavviata (nessuna cronologia precedente trovata).")
                else:
                    print("Rotazione API Key fallita. Non posso riprovare.")
                    return None
            else:
                print("Nessun'altra API key disponibile o raggiunto il numero massimo di tentativi.")
                return None
        finally:
            attempt += 1
    return None # Tutti i tentativi sono falliti


def end_gemini_chat() -> None:
    """
    Termina la sessione di chat corrente.

    Resetta la variabile globale `current_chat_session` a None. Questo assicura
    che ogni file PDF venga processato in una sessione di chat pulita e indipendente.
    """
    global current_chat_session
    if current_chat_session is not None:
        current_chat_session = None
        print("\n--- Sessione di chat Gemini terminata. ---")
    else:
        print("\nNessuna sessione di chat Gemini attiva da terminare.")


def process_pdf_to_json(args: argparse.Namespace) -> None:
    """
    Orchestra il processo di conversione da PDF a JSON per tutti i file nella cartella di input.

    Per ogni file PDF:
    1. Estrae il testo.
    2. Costruisce un prompt per Gemini, includendo o meno un template JSON.
    3. Invia il prompt e riceve una risposta.
    4. Pulisce e valida la risposta JSON, quindi la salva su file.
    """
    input_dir = args.inputPDF
    output_dir = args.outputJSON

    if not os.path.isdir(input_dir):
        print(f"ERRORE: La cartella di input '{input_dir}' non esiste.")
        return

    # Crea la cartella di output se non esiste.
    os.makedirs(output_dir, exist_ok=True)

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"Nessun file PDF trovato nella cartella '{input_dir}'.")
        return

    print(f"\nTrovati {len(pdf_files)} file PDF da processare.")

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_dir, pdf_file)
        json_filename = os.path.splitext(pdf_file)[0] + ".json"
        json_path = os.path.join(output_dir, json_filename)

        print(f"\n--- Processo il file: {pdf_file} ---")

        # Estrazione del testo dal PDF usando PyMuPDF (fitz).
        try:
            with fitz.open(pdf_path) as doc:
                pdf_text = "".join(page.get_text() for page in doc)
        except Exception as e:
            print(f"Errore durante la lettura del file PDF '{pdf_file}': {e}")
            continue # Salta al prossimo file

        # --- Costruzione dinamica del prompt per Gemini ---
        json_structure_description = ""
        prompt_template_section = ""
        prompt_rules_section = ""

        if not args.no_json_template:
            # Modalità 1: Utilizzo di un template JSON fornito dall'utente.
            if not args.json_template:
                print("ERRORE: Nessun template JSON fornito. Usa l'argomento --json-template o attiva --no-json-template.")
                return # Interrompe l'elaborazione di tutti i file.

            if os.path.exists(args.json_template):
                with open(args.json_template, 'r', encoding='utf-8') as f:
                    json_structure_description = f.read()
                print(f"Utilizzo della struttura JSON dal template: {args.json_template}")
                prompt_template_section = f"""
---
STRUTTURA JSON DA POPOLARE:
{json_structure_description}
---"""
                prompt_rules_section = """
REGOLE IMPORTANTI:
1. **Struttura Esatta**: La tua risposta DEVE seguire esattamente la struttura JSON definita. Non aggiungere o rimuovere chiavi.
2. **Tipi di Dati**: Rispetta i tipi di dato specificati (string, number). Per i numeri, non usare le virgolette.
3. **Dati Mancanti**: Se un'informazione non è presente nel testo, usa il valore `null` per la chiave corrispondente (non la stringa "null").
4. **Formato Data**: Dove richiesto, formatta le date come YYYY-MM-DD, se possibile."""
            else:
                print(f"ERRORE: Il file template JSON '{args.json_template}' non è stato trovato. Impossibile procedere.")
                continue # Salta al prossimo file PDF
        else:
            # Modalità 2: L'IA deve generare autonomamente la struttura JSON.
            print("Flag --no-json-template attivo. L'AI creerà la struttura JSON.")
            prompt_rules_section = """
REGOLE IMPORTANTI:
1. **Crea una Struttura Logica**: Definisci una struttura JSON chiara e gerarchica che organizzi in modo sensato le informazioni del documento.
2. **Dati Mancanti**: Se un'informazione non è presente nel testo, usa il valore `null` per la chiave corrispondente.
3. **Formato Data**: Dove possibile, formatta le date come YYYY-MM-DD."""

        # Assemblaggio del prompt finale.
        prompt = f"""
        Sei un assistente esperto nell'estrazione di dati da documenti finanziari e nella loro strutturazione in formato JSON.
        Analizza il testo seguente ed estrai le informazioni chiave.
        {prompt_rules_section}
        5. **Risposta Pulita**: La tua risposta deve contenere SOLO ed ESCLUSIVAMENTE il codice JSON. Non includere spiegazioni, commenti, o la marcatura ```json.{prompt_template_section}
        TESTO DEL DOCUMENTO DA ANALIZZARE:
        {pdf_text}
        ---
        """

        # Invia il prompt a Gemini e ottiene la risposta.
        json_response_text = start_gemini_chat(prompt)
        end_gemini_chat() # Termina la chat per processare ogni file in modo indipendente.

        if json_response_text:
            # --- Pulizia e Parsing della risposta JSON ---
            # L'IA dovrebbe restituire solo JSON, ma per robustezza si tenta di estrarlo
            # da blocchi di codice markdown (```json ... ```) o da oggetti JSON grezzi.
            match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*})', json_response_text)
            if match:
                # `match.groups()` contiene i risultati delle catture. Si cerca il primo
                # gruppo che non è None, che corrisponderà o al contenuto del blocco
                # markdown o all'oggetto JSON.
                json_data_str = next((g for g in match.groups() if g is not None), json_response_text)
            else:
                # Se la regex non trova corrispondenze, si assume che l'intera risposta sia il JSON.
                json_data_str = json_response_text

            # Rimuove spazi bianchi o newline iniziali/finali.
            json_data_str = json_data_str.strip()

            try:
                # Tenta di parsare la stringa pulita in un oggetto JSON Python.
                json_data = json.loads(json_data_str)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4, ensure_ascii=False)
                print(f"File JSON salvato con successo in: {json_path}")
            except json.JSONDecodeError:
                print(f"ERRORE: La risposta da Gemini per '{pdf_file}' non è un JSON valido.")
                # Salva la risposta grezza in un file di errore per il debug.
                with open(json_path + ".error.txt", 'w', encoding='utf-8') as f:
                    f.write(json_response_text)
        else:
            print(f"Non è stato possibile ottenere una risposta da Gemini per il file '{pdf_file}'.")


if __name__ == "__main__":
    # Punto di ingresso dello script.
    # 1. Analizza gli argomenti della riga di comando.
    args = get_args_parsed_main_updated()

    # 2. Inizializza le API key e il modello. Se fallisce, lo script termina.
    if initialize_api_keys_and_model(args):
        # 3. Avvia il processo principale di elaborazione dei PDF.
        process_pdf_to_json(args)
    else:
        print("Impossibile procedere senza un'inizializzazione valida dell'API Gemini.")