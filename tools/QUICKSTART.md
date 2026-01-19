# Quick Start: Synthetic Training Data Generation

## 1. Install API Client (Choose One)

```bash
# Option A: OpenAI (GPT-4)
pip install openai
export OPENAI_API_KEY="your-key-here"

# Option B: Anthropic (Claude)
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
```

## 2. Generate Training Data

```bash
# Generate 50 examples (takes ~5 minutes, costs ~$1-2)
python tools/generate_synthetic_training_data.py --count 50 --provider openai
```

## 3. Validate the Data

```bash
python tools/validate_training_data.py
```

## 4. Convert to Fine-Tuning Format

```bash
# For Unsloth/LoRA (recommended)
python tools/convert_to_finetuning_format.py --format unsloth

# Output will be in: data/finetuning/train_unsloth.jsonl
```

## 5. Fine-Tune Your Model

Now you can use the generated JSONL file with:
- **Unsloth** (recommended for LoRA fine-tuning)
- **Ollama** (if you converted to Modelfile format)
- Other fine-tuning frameworks

### Unsloth LoRA (Local)

```bash
# Fine-tune with Unsloth (creates adapter + Modelfile)
python tools/finetune_model.py \
  --model qwen2.5-3b \
  --train data/finetuning/train_unsloth.jsonl \
  --epochs 1 \
  --batch-size 2

# Create an Ollama model from the adapter
ollama create pockitect:finetuned -f data/finetuning/output/Modelfile

# Run the app against the fine-tuned model
export OLLAMA_MODEL=pockitect:finetuned
python run.sh
```

## Example: Full Pipeline

```bash
# 1. Generate
python tools/generate_synthetic_training_data.py --count 100 --provider openai

# 2. Validate
python tools/validate_training_data.py

# 3. Convert
python tools/convert_to_finetuning_format.py --format unsloth

# 4. Fine-tune (example with Unsloth)
python tools/finetune_model.py --model qwen2.5-3b --train data/finetuning/train_unsloth.jsonl

# 5. Load into Ollama
ollama create pockitect:finetuned -f data/finetuning/output/Modelfile
```

## Tips

- Start with 20-50 examples to test
- Validate after each batch
- Generate more examples for edge cases you discover
- Use `--delay 1.0` to slow down API calls if hitting rate limits
