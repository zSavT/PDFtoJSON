import os
import google.generativeai as genai
import json
import argparse
import fitz  # PyMuPDF
import re


# ----- COSTANTI GLOBALI -----
DEFAULT_MODEL_NAME = "gemini-2.5-flash" # Modello Gemini predefinito.

# ----- Variabili Globali -----
available_api_keys = []      # Lista API Caricate.
current_api_key_index = 0    # Indice della API key corrente
model = None                 # Modello Gemini
current_chat_session = None  # Variabile globale per la sessione di chat corrente


def get_args_parsed_main_updated():
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
    parsed_args = parser.parse_args()
    return parsed_args


def initialize_api_keys_and_model(args_parsed_main):
    global available_api_keys, current_api_key_index, model
    print("\n--- Inizializzazione API e Modello ---")
    if args_parsed_main.api:
        keys_from_arg = [key.strip() for key in args_parsed_main.api.split(',') if key.strip()]
        if keys_from_arg:
            available_api_keys.extend(keys_from_arg)
            print(f"{len(keys_from_arg)} API key(s) fornite tramite argomento --api.")
    api_key_file_path = "../api_key.txt"
    if os.path.exists(api_key_file_path):
        with open(api_key_file_path, "r") as f:
            keys_from_file = [line.strip() for line in f if line.strip()]
            if keys_from_file:
                available_api_keys.extend(keys_from_file)
                print(f"{len(keys_from_file)} API key(s) caricate da '{api_key_file_path}'.")
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

def rotate_api_key(args_parsed_main):
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
        current_api_key_index = previous_key_index
        try:
            genai.configure(api_key=available_api_keys[previous_key_index])
            model = genai.GenerativeModel(args_parsed_main.model_name)
            print("API Key precedente ripristinata.")
        except Exception as e_revert:
             print(f"Errore nel ripristino della API Key precedente: {e_revert}")
        return False

def start_gemini_chat(initial_prompt: str, max_attempts: int = 3) -> str | None:
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


def continue_gemini_chat(message: str, args, max_attempts: int = 3) -> str | None:
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


def end_gemini_chat():
    global current_chat_session
    if current_chat_session is not None:
        current_chat_session = None
        print("\n--- Sessione di chat Gemini terminata. ---")
    else:
        print("\nNessuna sessione di chat Gemini attiva da terminare.")


def process_pdf_to_json(args):
    """
    Funzione principale che orchestra il processo di conversione da PDF a JSON.
    """
    input_dir = args.inputPDF
    output_dir = args.outputJSON

    if not os.path.isdir(input_dir):
        print(f"ERRORE: La cartella di input '{input_dir}' non esiste.")
        return

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

        try:
            with fitz.open(pdf_path) as doc:
                pdf_text = "".join(page.get_text() for page in doc)
        except Exception as e:
            print(f"Errore durante la lettura del file PDF '{pdf_file}': {e}")
            continue # Salta al prossimo file

        # Carica la struttura JSON dal file template, se specificato
        json_structure_description = ""
        if args.json_template:
            if os.path.exists(args.json_template):
                with open(args.json_template, 'r', encoding='utf-8') as f:
                    json_structure_description = f.read()
                print(f"Utilizzo della struttura JSON dal template: {args.json_template}")
            else:
                print(f"ERRORE: Il file template JSON '{args.json_template}' non è stato trovato. Impossibile procedere.")
                continue # Salta al prossimo file PDF
        else:
            print("ERRORE: Nessun template JSON fornito. Usa l'argomento --json-template per specificare un file con la struttura desiderata.")
            # Interrompiamo l'elaborazione di tutti i file se manca il template
            return

        prompt = f"""
        Sei un assistente esperto nell'estrazione di dati e nella loro conversione in formato JSON.

        Analizza il testo seguente, che proviene da un documento di un prodotto finanziario (come un KIID o un Factsheet), ed estrai le informazioni richieste.
        Il tuo compito è popolare la struttura JSON fornita con i dati estratti dal testo.

        REGOLE IMPORTANTI:
        1. **Struttura Esatta**: La tua risposta DEVE seguire esattamente la struttura JSON definita qui sotto. Non aggiungere o rimuovere chiavi.
        2. **Tipi di Dati**: Rispetta i tipi di dato specificati (string, number). Per i numeri, non usare le virgolette.
        3. **Dati Mancanti**: Se un'informazione non è presente nel testo, usa il valore `null` per la chiave corrispondente (non la stringa "null").
        4. **Formato Data**: Dove richiesto, formatta le date come YYYY-MM-DD, se possibile.
        5. **Risposta Pulita**: La tua risposta deve contenere SOLO ed ESCLUSIVAMENTE il codice JSON. Non includere spiegazioni, commenti, o la marcatura ```json.

        ---
        STRUTTURA JSON DA POPOLARE:
        {json_structure_description}
        ---
        TESTO DEL DOCUMENTO DA ANALIZZARE:
        {pdf_text}
        ---
        """

        json_response_text = start_gemini_chat(prompt)
        end_gemini_chat() # Termina la chat per processare ogni file indipendentemente

        if json_response_text:
            # Pulisce la risposta per estrarre solo il JSON
            # IA dovrebbe restituire solo JSON, ma teniamo il cleaning per sicurezza.
            match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*})', json_response_text)
            if match:
                # Prendi il primo gruppo non nullo (o il contenuto del ```json``` o il JSON stesso)
                json_data_str = next((g for g in match.groups() if g is not None), json_response_text)
            else:
                json_data_str = json_response_text # Prova a usare la risposta così com'è

            json_data_str = json_data_str.strip()

            try:
                json_data = json.loads(json_data_str)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4, ensure_ascii=False)
                print(f"File JSON salvato con successo in: {json_path}")
            except json.JSONDecodeError:
                print(f"ERRORE: La risposta da Gemini per '{pdf_file}' non è un JSON valido.")
                # Opzionale: salva la risposta grezza per il debug
                with open(json_path + ".error.txt", 'w', encoding='utf-8') as f:
                    f.write(json_response_text)
        else:
            print(f"Non è stato possibile ottenere una risposta da Gemini per il file '{pdf_file}'.")


if __name__ == "__main__":
    args = get_args_parsed_main_updated()
    if initialize_api_keys_and_model(args):
        process_pdf_to_json(args)
    else:
        print("Impossibile procedere senza un'inizializzazione valida dell'API Gemini.")