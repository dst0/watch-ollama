import requests
import time
import json

# Generate a small prompt (approx 1k tokens)
repeat_text = "The quick brown fox jumps over the lazy dog. " * 50 
large_prompt = "Summarize the following: " + (repeat_text + "\n") * 2

url = "http://localhost:11435/api/generate"
payload = {
    "model": "qwen3.6-35b-64k",
    "prompt": large_prompt,
    "stream": False
}

print(f"Sending request with prompt length: {len(large_prompt)} characters...")
start_time = time.time()
response = requests.post(url, json=payload)
end_time = time.time()

if response.status_code == 200:
    data = response.json()
    total_duration = data.get('total_duration', 0) / 1e9
    load_duration = data.get('load_duration', 0) / 1e9
    prompt_eval_count = data.get('prompt_eval_count', 0)
    prompt_eval_duration = data.get('prompt_eval_duration', 0) / 1e9
    eval_count = data.get('eval_count', 0)
    eval_duration = data.get('eval_duration', 0) / 1e9
    
    print("\n--- Benchmark Results ---")
    print(f"Total Time (Wall Clock): {end_time - start_time:.2f}s")
    print(f"Ollama Total Duration: {total_duration:.2f}s")
    print(f"Prompt Tokens: {prompt_eval_count}")
    print(f"Prompt Processing Speed: {prompt_eval_count / prompt_eval_duration:.2f} tokens/s")
    print(f"Generation Tokens: {eval_count}")
    print(f"Generation Speed: {eval_count / eval_duration:.2f} tokens/s")
    print(f"Response: {data.get('response', '')[:100]}...")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
