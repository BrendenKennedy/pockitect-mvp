#!/usr/bin/env python3
"""
Fine-tune a local model using Unsloth LoRA.

Example:
    python tools/finetune_model.py --model llama3.2 --train data/finetuning/train_unsloth.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from finetuning_config import get_preset


def _require_unsloth():
    try:
        from unsloth import FastLanguageModel  # type: ignore
        from trl import SFTTrainer  # type: ignore
        from transformers import TrainingArguments, EarlyStoppingCallback  # type: ignore
        from datasets import load_dataset  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Unsloth dependencies are not available. Install with:\n"
            "  pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\"\n"
            "And ensure torch, transformers, datasets, and trl are installed."
        ) from exc

    return FastLanguageModel, SFTTrainer, TrainingArguments, load_dataset, EarlyStoppingCallback


def _write_modelfile(output_dir: Path, base_model: str, adapter_dir: Path) -> Path:
    modelfile = output_dir / "Modelfile"
    modelfile.write_text(
        "\n".join(
            [
                f"FROM {base_model}",
                "PARAMETER temperature 0.2",
                f"ADAPTER {adapter_dir}",
            ]
        ),
        encoding="utf-8",
    )
    return modelfile


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune Pockitect model with Unsloth.")
    parser.add_argument("--model", required=True, help="Base model name (e.g., llama3.2, qwen3)")
    parser.add_argument("--train", required=True, type=Path, help="JSONL training file path")
    parser.add_argument("--output-dir", default=Path("data/finetuning/output"), type=Path)
    parser.add_argument("--preset", default=None, help="Optional model preset (llama3.2, qwen3, mistral7b)")
    parser.add_argument("--max-seq-len", type=int, default=2048)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--save-steps", type=int, default=200)
    parser.add_argument("--logging-steps", type=int, default=25)
    parser.add_argument("--early-stopping", action="store_true", help="Enable early stopping based on validation loss")
    parser.add_argument("--early-stopping-patience", type=int, default=3, help="Number of eval steps with no improvement before stopping")
    parser.add_argument("--eval-split", type=float, default=0.1, help="Fraction of data to use for validation (0.1 = 10%%)")
    parser.add_argument("--eval-steps", type=int, default=50, help="Evaluate every N steps")

    args = parser.parse_args()

    if not args.train.exists():
        print(f"Training file not found: {args.train}")
        return 1

    preset = get_preset(args.preset)
    max_seq_len = preset.max_seq_len if preset else args.max_seq_len
    load_in_4bit = preset.load_in_4bit if preset else True

    # Avoid fused CE loss auto-detection when free VRAM is very low.
    os.environ.setdefault("UNSLOTH_CE_LOSS_TARGET_GB", "0.2")

    FastLanguageModel, SFTTrainer, TrainingArguments, load_dataset, EarlyStoppingCallback = _require_unsloth()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading dataset: {args.train}")
    full_dataset = load_dataset("json", data_files=str(args.train), split="train")

    # Split dataset for validation if early stopping is enabled
    eval_dataset = None
    if args.early_stopping:
        split = full_dataset.train_test_split(test_size=args.eval_split, seed=42)
        dataset = split["train"]
        eval_dataset = split["test"]
        print(f"Split dataset: {len(dataset)} train, {len(eval_dataset)} eval")
    else:
        dataset = full_dataset

    print(f"Loading base model: {args.model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=max_seq_len,
        dtype=None,
        load_in_4bit=load_in_4bit,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # Detect GPU capability for fp16/bf16 selection
    # bf16 requires Ampere+ (compute capability 8.0+), T4 is 7.5
    import torch
    use_bf16 = False
    use_fp16 = False
    if torch.cuda.is_available():
        capability = torch.cuda.get_device_capability()
        if capability[0] >= 8:  # Ampere or newer
            use_bf16 = True
            print(f"GPU compute capability {capability[0]}.{capability[1]} - using bf16")
        else:
            use_fp16 = True
            print(f"GPU compute capability {capability[0]}.{capability[1]} - using fp16 (bf16 requires Ampere+)")

    # Build training arguments
    training_kwargs = dict(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.lr,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        fp16=use_fp16,
        bf16=use_bf16,
        optim="adamw_8bit",
        report_to="none",
    )

    # Add evaluation settings if early stopping is enabled
    if args.early_stopping:
        training_kwargs.update(
            eval_strategy="steps",
            eval_steps=args.eval_steps,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
        )

    training_args = TrainingArguments(**training_kwargs)

    def _format_single(instruction, inp, output):
        parts = [instruction or "", inp or "", output or ""]
        parts = [p.strip() for p in parts if p]
        return "\n\n".join(parts)

    def formatting_func(example):
        instruction = example.get("instruction")
        inp = example.get("input")
        output = example.get("output")

        if isinstance(instruction, list):
            texts = []
            for i, inst in enumerate(instruction):
                in_i = inp[i] if isinstance(inp, list) else ""
                out_i = output[i] if isinstance(output, list) else ""
                texts.append(_format_single(inst, in_i, out_i))
            return texts

        return [_format_single(instruction, inp, output)]

    # Build trainer kwargs
    trainer_kwargs = dict(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        formatting_func=formatting_func,
        max_seq_length=max_seq_len,
        args=training_args,
    )

    # Add eval dataset and early stopping callback if enabled
    callbacks = []
    if args.early_stopping:
        trainer_kwargs["eval_dataset"] = eval_dataset
        callbacks.append(EarlyStoppingCallback(early_stopping_patience=args.early_stopping_patience))
        print(f"Early stopping enabled: patience={args.early_stopping_patience}, eval every {args.eval_steps} steps")

    if callbacks:
        trainer_kwargs["callbacks"] = callbacks

    trainer = SFTTrainer(**trainer_kwargs)

    print("Starting fine-tuning...")
    trainer.train()

    # Report if early stopping triggered
    if args.early_stopping and trainer.state.global_step < (len(dataset) // args.batch_size) * args.epochs:
        print(f"⚠️  Early stopping triggered at step {trainer.state.global_step}")

    adapter_dir = output_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    modelfile = _write_modelfile(output_dir, args.model, adapter_dir)
    print(f"Saved adapter: {adapter_dir}")
    print(f"Saved Modelfile: {modelfile}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
