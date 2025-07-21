import os
import google.generativeai as genai
import json
import argparse
from argparse_color_formatter import ColorHelpFormatter

#--COSTANTI GLOBALI--
DEFAULT_MODEL_NAME = "gemini-2.5-flash" # Modello Gemini predefinito


def get_script_args_updated():
    global script_args
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
    script_args = parsed_args
    return parsed_args


if __name__ == "__main__":
  print("Hello")
  args_parsed_main = get_script_args_updated()
