import os
import google.generativeai as genai
import json
import argparse


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
                        help="Percorso della cartella dove è presente il file PDF.\nDefault: 'input'")
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


def continue_gemini_chat(message: str, max_attempts: int = 3) -> str | None:
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


if __name__ == "__main__":
    args = get_args_parsed_main_updated()
    if initialize_api_keys_and_model(args):
        # --- Esempio di utilizzo della funzione start_gemini_chat ---
        initial_prompt = "Ciao Gemini, puoi darmi una curiosità sul sistema solare?"
        response_text = start_gemini_chat(initial_prompt)

        if response_text:
            print("\n--- Risposta Iniziale da Gemini ---")
            print(response_text)

            # --- Esempio di utilizzo della funzione continue_gemini_chat ---
            second_message = "Interessante! E qual è il pianeta più grande?"
            response_text_2 = continue_gemini_chat(second_message)

            if response_text_2:
                print("\n--- Risposta Continua da Gemini ---")
                print(response_text_2)

                # --- Un altro messaggio per continuare ---
                third_message = "E quale il più piccolo?"
                response_text_3 = continue_gemini_chat(third_message)

                if response_text_3:
                    print("\n--- Risposta Continua da Gemini (2) ---")
                    print(response_text_3)
            else:
                print("\nNon è stato possibile ottenere una risposta di continuazione da Gemini.")
        else:
            print("\nNon è stato possibile ottenere una risposta iniziale da Gemini dopo vari tentativi.")

        # --- Esempio di utilizzo della funzione end_gemini_chat ---
        end_gemini_chat()

        # Tentativo di continuare una chat dopo averla terminata (dovrebbe dare errore)
        print("\n--- Tentativo di continuare una chat dopo averla terminata ---")
        response_after_end = continue_gemini_chat("Questo messaggio non dovrebbe andare a buon fine.")
        if response_after_end is None:
            print("Confermato: non è possibile continuare una chat terminata.")

        # Avvio di una nuova chat dopo averne terminata una
        print("\n--- Avvio di una nuova chat dopo averne terminata una ---")
        new_chat_response = start_gemini_chat("Inizia una nuova conversazione: qual è la capitale dell'Italia?")
        if new_chat_response:
            print("\n--- Risposta Nuova Chat ---")
            print(new_chat_response)

    else:
        print("Impossibile procedere senza un'inizializzazione valida dell'API Gemini.")