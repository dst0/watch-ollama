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
    
    # Standardized Parameters
    ctx = input("Context length [32768]: ") or "32768"
    threads = input("Number of threads [4]: ") or "4"
    batch = input("Batch size [512]: ") or "512"
    
    num_ctx = f"PARAMETER num_ctx {ctx}"
    num_thread = f"PARAMETER num_thread {threads}"
    num_batch = f"PARAMETER num_batch {batch}"
    
    print("Generate Modelfile content...")
    content = f"FROM {model_path}\n{num_ctx}\n{num_thread}\n{num_batch}\n"
    
    # System Prompt / Tools Support
    print("Optional: Enter a System Prompt (or path to a system prompt file).")
    sys_prompt = input("System prompt: ")
    if sys_prompt:
        # If it's a file path, read it
        if os.path.exists(sys_prompt):
            with open(sys_prompt, "r") as f:
                content += f"SYSTEM \"{f.read()}\"\n"
        else:
            content += f"SYSTEM \"{sys_prompt}\"\n"
            
    with open(f"Modelfile-{model_name}", "w") as f:
        f.write(content)
        
    print(f"Modelfile-{model_name} generated successfully.")

if __name__ == "__main__":
    generate_modelfile()
