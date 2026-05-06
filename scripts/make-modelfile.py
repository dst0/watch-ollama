#!/usr/bin/env python3
import os
import sys

def find_gguf_files():
    # Search common directories for GGUF files
    search_dirs = [os.path.expanduser("~/models"), os.getcwd()]
    gguf_files = []
    for d in search_dirs:
        if os.path.exists(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith(".gguf"):
                        gguf_files.append(os.path.join(root, f))
    return gguf_files

def generate_modelfile():
    print("--- Ollama Modelfile Generator ---")
    files = find_gguf_files()
    if not files:
        print("No .gguf files found. Please place them in ~/models or current dir.")
        return

    print("Found files:")
    for i, f in enumerate(files):
        print(f"{i+1}: {f}")
    
    choice = int(input("Select file index: ")) - 1
    model_path = files[choice]
    model_name = input("Enter model name (e.g., my-model): ")
    ctx = input("Context length (e.g., 32768): ") or "32768"
    threads = input("Number of threads (e.g., 4): ") or "4"
    batch = input("Batch size (e.g., 256): ") or "256"
    
    num_ctx = f"PARAMETER num_ctx {ctx}"
    num_thread = f"PARAMETER num_thread {threads}"
    num_batch = f"PARAMETER num_batch {batch}"
    
    print("Generate Modelfile content...")
    content = f"FROM {model_path}\n{num_ctx}\n{num_thread}\n{num_batch}\n"
    
    # Optional System Prompt
    sys_prompt = input("System prompt (leave blank for default): ")
    if sys_prompt:
        content += f"SYSTEM \"{sys_prompt}\"\n"
        
    with open(f"Modelfile-{model_name}", "w") as f:
        f.write(content)
        
    print(f"Modelfile-{model_name} generated successfully.")

if __name__ == "__main__":
    generate_modelfile()
