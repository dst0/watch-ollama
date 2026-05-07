import pathlib
import subprocess
import sys

_INSTALL_DIR = pathlib.Path(__file__).resolve().parent.parent
READABLE_LOG = str(_INSTALL_DIR / "ollama_readable.log")

def copy_last_response():
    try:
        with open(READABLE_LOG, 'r') as f:
            content = f.read()

        # Split by generation finished markers
        parts = content.split('[GENERATION FINISHED]')
        if len(parts) < 2:
            print("No complete response found.")
            return

        # Get the last part and extract the response
        last_response = parts[-2]
        # Content usually appears after the prompt/assistant marker
        # Looking for the last occurrence of '### ASSISTANT' or similar markers
        
        # Simplified: take everything after the last '### ASSISTANT'
        marker = '### ASSISTANT'
        if marker in last_response:
            response_body = last_response.split(marker)[-1].strip()
        else:
            # Fallback if no marker
            lines = last_response.splitlines()
            response_body = "\n".join([line for line in lines if not line.startswith('| ') and not line.startswith('[')]).strip()

        if not response_body:
            print("Could not find response content.")
            return

        process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
        process.communicate(input=response_body.encode('utf-8'))
        print("Last response copied to clipboard.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    copy_last_response()
