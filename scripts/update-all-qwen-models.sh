#!/bin/bash
# Batch update script for all Qwen3.6 models to include tool support

# Get the list of all Qwen3.6 models
MODELS=$(ollama list | grep -i "Qwen3.6" | awk '{print $1}')

# Get the template
cp scripts/tool_template.txt tool_template.txt

for model in $MODELS; do
    echo "Updating $model with tool support and parameters..."
    
    # Extract existing FROM line
    ollama show --modelfile "$model" > "Modelfile-$model"
    FROM_LINE=$(grep "FROM" "Modelfile-$model")
    
    # Create new Modelfile with FROM line, template, and parameters
    echo "$FROM_LINE" > "new_modelfile.txt"
    cat tool_template.txt >> "new_modelfile.txt"
    echo "PARAMETER num_thread 4" >> "new_modelfile.txt"
    echo "PARAMETER num_batch 512" >> "new_modelfile.txt"
    echo "PARAMETER num_ctx 32768" >> "new_modelfile.txt"
    echo "PARAMETER num_predict -1" >> "new_modelfile.txt"
    
    # Create/Overwrite the model
    ollama create "$model" -f "new_modelfile.txt"
    
    # Cleanup
    rm "Modelfile-$model" "new_modelfile.txt"
done

rm template_source.txt tool_template.txt
