# Pockitect Training Data Tools

Tools for generating, validating, and converting training data for fine-tuning the Pockitect AI model.

## Overview

These tools help you:
1. **Generate synthetic training data** using GPT-4 or Claude API
2. **Validate training data** quality and schema compliance
3. **Convert training data** to fine-tuning formats (Ollama, Unsloth, Alpaca, ChatML)

## Setup

### Install Optional Dependencies

For synthetic data generation, install one of:

```bash
# For OpenAI (GPT-4)
pip install openai

# For Anthropic (Claude)
pip install anthropic
```

Set your API key:

```bash
export OPENAI_API_KEY="your-key-here"
# or
export ANTHROPIC_API_KEY="your-key-here"
```

## Usage

### 1. Generate Synthetic Training Data

Generate diverse training examples automatically:

```bash
# Generate 50 examples using OpenAI
python tools/generate_synthetic_training_data.py --count 50 --provider openai

# Generate 100 examples using Anthropic
python tools/generate_synthetic_training_data.py --count 100 --provider anthropic

# Use a specific model
python tools/generate_synthetic_training_data.py --count 50 --provider openai --model gpt-4-turbo-preview

# Custom output directory
python tools/generate_synthetic_training_data.py --count 50 --output-dir data/training/custom
```

**Options:**
- `--count`: Number of examples to generate (default: 50)
- `--provider`: `openai` or `anthropic` (default: openai)
- `--model`: Model name (defaults to best model for provider)
- `--output-dir`: Output directory (default: `data/training`)
- `--delay`: Delay between API calls in seconds (default: 0.5)

**Cost Estimates:**
- GPT-4 Turbo: ~$0.01-0.03 per example → 100 examples ≈ $1-3
- Claude 3.5 Sonnet: ~$0.015 per example → 100 examples ≈ $1.50

### 2. Validate Training Data

Check all training files for errors and warnings:

```bash
# Validate all training data
python tools/validate_training_data.py

# Validate custom directory
python tools/validate_training_data.py --training-dir data/training/custom
```

The validator checks:
- ✅ Required fields are present
- ✅ JSON is valid
- ✅ Schema matches expected structure
- ✅ Prompts are non-empty
- ✅ YAML data can be merged with defaults

### 3. Convert to Fine-Tuning Format

Convert training data to formats compatible with fine-tuning tools:

```bash
# Convert to Unsloth format (recommended for LoRA)
python tools/convert_to_finetuning_format.py --format unsloth

# Convert to Ollama Modelfile format
python tools/convert_to_finetuning_format.py --format ollama

# Convert to Alpaca format
python tools/convert_to_finetuning_format.py --format alpaca

# Convert to ChatML format
python tools/convert_to_finetuning_format.py --format chatml

# Custom output file
python tools/convert_to_finetuning_format.py --format unsloth --output data/finetuning/my_train.jsonl
```

**Supported Formats:**
- `unsloth`: JSONL format for Unsloth/LoRA fine-tuning (recommended)
- `ollama`: Modelfile format for Ollama fine-tuning
- `alpaca`: Alpaca instruction format
- `chatml`: ChatML message format

## Workflow

### Recommended Workflow

1. **Generate synthetic data:**
   ```bash
   python tools/generate_synthetic_training_data.py --count 100 --provider openai
   ```

2. **Validate the data:**
   ```bash
   python tools/validate_training_data.py
   ```

3. **Fix any validation errors** (manually or regenerate)

4. **Convert to fine-tuning format:**
   ```bash
   python tools/convert_to_finetuning_format.py --format unsloth
   ```

5. **Fine-tune your model** using the generated JSONL file

### Example: Complete Pipeline

```bash
# 1. Generate 50 examples
python tools/generate_synthetic_training_data.py --count 50 --provider openai

# 2. Validate
python tools/validate_training_data.py

# 3. If validation passes, convert
python tools/convert_to_finetuning_format.py --format unsloth

# 4. Now you have data/finetuning/train_unsloth.jsonl ready for fine-tuning!
```

## Training Data Format

Training data is stored as pairs of files:

```
data/training/
├── 001-simple-blog.prompt.txt    # Natural language prompt
├── 001-simple-blog.json          # Corresponding YAML blueprint (as JSON)
├── 002-static-website.prompt.txt
├── 002-static-website.json
└── ...
```

### Prompt Format

Natural language description of infrastructure needs:
```
Create a simple blog backend with:
- A small EC2 instance (t3.micro) running Ubuntu
- Open ports for SSH (22), HTTP (80), and HTTPS (443)
- A PostgreSQL database with 20GB storage
- Generate a new SSH key pair
- Deploy in US East (Ohio) region
```

### JSON Format

Valid YAML blueprint structure (as JSON):
```json
{
  "project": {
    "name": "simple-blog",
    "description": "A simple blog backend",
    "region": "us-east-2",
    "owner": "developer"
  },
  "network": {
    "vpc_mode": "default",
    "subnet_type": "public",
    "rules": [...]
  },
  ...
}
```

## Tips

1. **Start small**: Generate 20-50 examples first, validate, then generate more
2. **Diversity matters**: The generator automatically varies scenarios and phrasing
3. **Validate early**: Run validation after each batch to catch issues
4. **Iterate**: Generate more examples for edge cases you discover during testing
5. **Cost control**: Use `--delay` to slow down API calls and monitor costs

## Troubleshooting

### API Key Not Found
```
Error: OPENAI_API_KEY environment variable not set
```
Solution: Set your API key: `export OPENAI_API_KEY="your-key"`

### Import Errors
```
ImportError: OpenAI package not installed
```
Solution: `pip install openai` or `pip install anthropic`

### Validation Errors
If validation finds errors, check:
- JSON syntax is valid
- Required fields are present (project, network, compute, data, security)
- project.name is not empty
- Network rules have port, protocol, and cidr

### Low Quality Examples
If generated examples are low quality:
- Try a different model (e.g., `gpt-4-turbo-preview` vs `gpt-3.5-turbo`)
- Increase temperature (already set to 0.9 for diversity)
- Generate more examples and filter the best ones

## 4. Migrate Training Data to Canonical Format

If you have existing training examples that use the old schema (with `vpc_mode`, etc.), 
migrate them to the canonical format that matches your project blueprint structure:

```bash
# Dry run to see what would be changed
python tools/migrate_training_to_canonical.py --dry-run

# Create backup and migrate
python tools/migrate_training_to_canonical.py --backup

# After migration, regenerate the JSONL file
python tools/convert_to_finetuning_format.py --format unsloth
```

**What gets migrated:**
- `vpc_mode: "default"` → `vpc_env: "prod"`
- `vpc_mode: "new"` → `vpc_env: "dev"`
- Adds missing fields: `vpc_id`, `subnet_id`, `security_group_id`, `status` fields
- Expands `key_pair`, `certificate`, `iam_role` to include all canonical fields
- Ensures all sections match the canonical blueprint structure

## Next Steps

After generating and converting training data:

1. **Fine-tune with Unsloth** (recommended):
   ```bash
   # Install unsloth
   pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
   
   # Fine-tune (see Unsloth documentation)
   ```

2. **Fine-tune with Ollama**:
   - Use the generated Modelfile
   - See Ollama fine-tuning documentation

3. **Test the fine-tuned model**:
   - Use it in your Pockitect AI agent
   - Compare results with base model
