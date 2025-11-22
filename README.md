# PDFtoJSON

`PDFtoJSON` è uno script Python da riga di comando che utilizza l'intelligenza artificiale di Google Gemini per estrarre dati strutturati da file PDF e convertirli in formato JSON. È progettato per essere flessibile e robusto, gestendo la rotazione automatica delle API key e consentendo la definizione di strutture JSON personalizzate tramite template.

## Funzionalità Principali

- **Conversione da PDF a JSON**: Processa uno o più file PDF da una cartella di input e genera i corrispondenti file JSON in una cartella di output.
- **Intelligenza Artificiale Gemini**: Sfrutta i modelli generativi di Google (es. `gemini-2.5-flash`) per l'analisi del testo e l'estrazione dei dati.
- **Struttura JSON Configurabile**: Permette di specificare una struttura JSON desiderata tramite un file di template, guidando l'IA per ottenere un output consistente e prevedibile.
- **Estrazione Automatica della Struttura**: In alternativa, può analizzare il documento e proporre autonomamente una struttura JSON logica, senza bisogno di un template predefinito.
- **Rotazione Automatica delle API Key**: Supporta l'uso di più API key e le ruota automaticamente in caso di errori (es. limiti di quota), aumentando la resilienza dello script.
- **Configurazione Flessibile**: Gestione delle API key sia tramite argomenti da riga di comando sia tramite un file di configurazione dedicato.

## Prerequisiti

- Python 3.8 o superiore.
- Accesso a una o più API key di Google Gemini.

## Installazione

1.  Clona il repository sul tuo sistema locale:
    ```bash
    git clone <URL_DEL_TUO_REPOSITORY>
    cd PDFtoJSON
    ```

2.  Si consiglia di creare un ambiente virtuale per isolare le dipendenze del progetto:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Su Windows: venv\Scripts\activate
    ```

3.  Installa le librerie Python necessarie tramite il file `requirements.txt`:
    ```bash
    pip install -r src/requirements.txt
    ```

## Configurazione delle API Key

Lo script può ottenere le API key di Gemini in due modi (con priorità al primo):

1.  **File `api_key.txt` (Consigliato)**:
    Crea un file chiamato `api_key.txt` nella directory principale del progetto (accanto alla cartella `src`) e inserisci una API key per riga. Questo metodo è ideale per gestire più chiavi.
    ```
    # api_key.txt
    AIzaSy...key1
    AIzaSy...key2
    ```

2.  **Argomento `--api`**:
    Specifica una o più chiavi direttamente dalla riga di comando, separate da una virgola.
    ```bash
    python src/PDFtoJSON.py --api "AIzaSy...key1,AIzaSy...key2" ...
    ```

## Utilizzo

Lo script viene eseguito dalla riga di comando e offre due modalità principali di funzionamento.
Prima di eseguirlo, posiziona i file PDF da processare nella cartella `input` (o in un'altra specificata con `--inputPDF`).

### 1. Con Template JSON (Modalità Consigliata)

Fornisci un file di template (`--json-template`) che definisce la struttura esatta del JSON di output. Questo garantisce consistenza e prevedibilità, specialmente quando si processano più documenti dello stesso tipo.

**Comando di esempio:**
```bash
python src/PDFtoJSON.py --json-template "path/to/your/template.json"
```

### 2. Senza Template JSON (Modalità Automatica)

Utilizza il flag `--no-json-template` per lasciare che sia l'IA a definire la struttura JSON più appropriata in base al contenuto del documento. Questa modalità è utile per l'esplorazione iniziale dei dati o quando non si dispone di una struttura fissa.

**Comando di esempio:**
```bash
python src/PDFtoJSON.py --no-json-template
```

### Argomenti della Riga di Comando

- `--inputPDF`: Percorso della cartella di input contenente i file PDF (default: `input`).
- `--outputJSON`: Percorso della cartella di output dove salvare i file JSON (default: `output`).
- `--json-template`: Percorso del file (`.json` o `.txt`) contenente la struttura JSON da usare come template. **Obbligatorio se non si usa `--no-json-template`**.
- `--no-json-template`: Se attivo, lo script non userà un template e chiederà all'IA di generare una struttura JSON appropriata in base al contenuto del PDF.
- `--api`: Stringa contenente una o più API key separate da virgola.
- `--model-name`: Nome del modello Gemini da utilizzare (default: `gemini-2.5-flash`).
