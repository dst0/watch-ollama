#!/bin/bash
# Batch update script for all Qwen3.6 models to include tool support

# Get the list of all Qwen3.6 models
MODELS=$(ollama list | grep -i "Qwen3.6" | awk '{print $1}')

# Get the template

for model in $MODELS; do
    echo "Updating $model with official template and parameters..."
    
    # Extract existing FROM line
    ollama show --modelfile "$model" > "Modelfile-$model"
    FROM_LINE=$(grep "FROM" "Modelfile-$model")
    
    # Create new Modelfile: FROM line + base template
    echo "$FROM_LINE" > "new_modelfile.txt"
    cat Qwen3.6.template >> "new_modelfile.txt"
    
    # Create/Overwrite the model
    ollama create "$model" -f "new_modelfile.txt"
    
    # Cleanup
    rm "Modelfile-$model" "new_modelfile.txt"
done
