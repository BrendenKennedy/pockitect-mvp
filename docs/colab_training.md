Colab Training Guide (Unsloth)

This guide runs fine-tuning on a GPU-backed Colab runtime.

1) Open a new Colab notebook
2) Runtime → Change runtime type → GPU (T4/A100/L4)

3) Clone the repo
```bash
!git clone https://github.com/<your-org-or-user>/pocket-architect-mvp.git
%cd pocket-architect-mvp
```

4) Install dependencies
```bash
!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install -r requirements.txt
```

5) (Optional) Validate training data
```bash
!python tools/validate_training_data.py
```

6) (Optional) Regenerate JSONL if you changed training data
```bash
!python tools/convert_to_finetuning_format.py --format unsloth
```

7) Train
```bash
!python tools/finetune_model.py --model qwen2.5-3b --train data/finetuning/train_unsloth.jsonl --epochs 1 --batch-size 2
```

8) Create an Ollama model (optional)
```bash
!ollama create pockitect:finetuned -f data/finetuning/output/Modelfile
```

Notes
- If you don't want to clone the repo, upload the folder or zip directly.
- Colab may reset the runtime. Re-run install steps after reconnecting.
