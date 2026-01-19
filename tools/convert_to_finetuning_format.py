#!/usr/bin/env python3
"""
Convert Pockitect training data to fine-tuning format.

Supports multiple formats:
- Ollama Modelfile format
- Unsloth/LoRA format (JSONL)
- Alpaca format (JSONL)

Usage:
    python tools/convert_to_finetuning_format.py --format ollama
    python tools/convert_to_finetuning_format.py --format unsloth --output data/finetuning/train.jsonl
"""

import json
import sys
import argparse
import re
import yaml
from pathlib import Path
from typing import Dict, List

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from storage import create_empty_blueprint


class FineTuningConverter:
    def __init__(self, training_dir: Path):
        self.training_dir = training_dir

    def _extract_block(self, text: str, tag: str) -> tuple[str | None, str]:
        pattern = rf"\\[{tag}\\]\\s*(.*?)\\s*\\[/{tag}\\]"
        match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return None, text
        block = match.group(1).strip()
        cleaned = (text[:match.start()] + text[match.end():]).strip()
        return block, cleaned

    def _parse_prompt(self, prompt_text: str) -> tuple[str, dict[str, str]]:
        meta: dict[str, str] = {}
        history, remainder = self._extract_block(prompt_text, "history")
        if history:
            meta["history"] = history
            prompt_text = remainder

        tool_sim, remainder = self._extract_block(prompt_text, "tool_simulation")
        if tool_sim:
            meta["tool_simulation"] = tool_sim
            prompt_text = remainder

        prompt_text = prompt_text.strip()
        return prompt_text, meta
    
    def load_training_pairs(self) -> List[Dict]:
        """Load all prompt/YAML pairs from training directory."""
        pairs = []
        
        for prompt_file in sorted(self.training_dir.glob("*.prompt.txt")):
            # JSON file has same name but .json extension instead of .prompt.txt
            json_file = prompt_file.parent / (prompt_file.stem.replace(".prompt", "") + ".json")
            
            if not json_file.exists():
                print(f"⚠️  Skipping {prompt_file.name}: missing {json_file.name}")
                continue
            
            try:
                raw_prompt = prompt_file.read_text(encoding="utf-8").strip()
                prompt, meta = self._parse_prompt(raw_prompt)
                yaml_data = json.loads(json_file.read_text(encoding="utf-8"))
                
                pairs.append({
                    "prompt": prompt,
                    "yaml": yaml_data,
                    "meta": meta,
                    "name": prompt_file.stem.replace(".prompt", "")
                })
            except Exception as e:
                print(f"⚠️  Skipping {prompt_file.name}: {e}")
                continue
        
        return pairs
    
    def build_context(self, yaml_data: Dict) -> str:
        """Build context string for the prompt (AWS state, schema, etc.)."""
        # Get schema from example blueprint
        schema_example = create_empty_blueprint("example-project")
        schema_definition = yaml.dump(schema_example, default_flow_style=False, sort_keys=False)
        
        # Simplified context (you can enhance this with actual AWS state)
        context = f"""YAML Schema:
{schema_definition}

Generate ONLY valid YAML matching the schema above. No explanations, just YAML."""
        
        return context

    def _build_prompt_prefix(self, meta: Dict[str, str]) -> str:
        sections = []
        history = meta.get("history")
        if history:
            sections.append(f"Conversation History:\n{history}\n")
        tool_sim = meta.get("tool_simulation")
        if tool_sim:
            sections.append(f"Tool Simulation:\n{tool_sim}\n")
        return "\n".join(sections) + ("\n" if sections else "")
    
    def convert_to_ollama_format(self, pairs: List[Dict]) -> str:
        """Convert to Ollama Modelfile format."""
        lines = []
        
        for pair in pairs:
            prompt = pair["prompt"]
            yaml_content = yaml.dump(pair["yaml"], default_flow_style=False, sort_keys=False)
            context = self.build_context(pair["yaml"])
            prefix = self._build_prompt_prefix(pair.get("meta", {}))
            
            # Ollama format uses special tokens
            lines.append(f"<|user|>")
            lines.append(f"{prefix}{context}\n\nUser Request: {prompt}")
            lines.append(f"<|assistant|>")
            lines.append(f"```yaml\n{yaml_content}\n```")
            lines.append("")  # Empty line between examples
        
        return "\n".join(lines)
    
    def convert_to_unsloth_format(self, pairs: List[Dict]) -> List[Dict]:
        """Convert to Unsloth/LoRA format (JSONL)."""
        examples = []
        
        for pair in pairs:
            prompt = pair["prompt"]
            yaml_content = yaml.dump(pair["yaml"], default_flow_style=False, sort_keys=False)
            context = self.build_context(pair["yaml"])
            prefix = self._build_prompt_prefix(pair.get("meta", {}))
            
            # Build full prompt
            full_prompt = f"""{prefix}{context}

User Request: {prompt}

Generate the YAML blueprint:"""
            
            # Unsloth format
            example = {
                "instruction": full_prompt,
                "input": "",
                "output": f"```yaml\n{yaml_content}\n```"
            }
            
            examples.append(example)
        
        return examples
    
    def convert_to_alpaca_format(self, pairs: List[Dict]) -> List[Dict]:
        """Convert to Alpaca format (JSONL)."""
        examples = []
        
        for pair in pairs:
            prompt = pair["prompt"]
            yaml_content = yaml.dump(pair["yaml"], default_flow_style=False, sort_keys=False)
            context = self.build_context(pair["yaml"])
            prefix = self._build_prompt_prefix(pair.get("meta", {}))
            
            # Alpaca format
            example = {
                "instruction": f"{prefix}{context}\n\nUser Request: {prompt}",
                "input": "",
                "output": f"```yaml\n{yaml_content}\n```"
            }
            
            examples.append(example)
        
        return examples
    
    def convert_to_chatml_format(self, pairs: List[Dict]) -> List[Dict]:
        """Convert to ChatML format (for models that support it)."""
        examples = []
        
        for pair in pairs:
            prompt = pair["prompt"]
            yaml_content = yaml.dump(pair["yaml"], default_flow_style=False, sort_keys=False)
            context = self.build_context(pair["yaml"])
            prefix = self._build_prompt_prefix(pair.get("meta", {}))
            
            example = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an AWS infrastructure assistant for Pockitect. Generate valid YAML blueprints that match the schema."
                    },
                    {
                        "role": "user",
                        "content": f"{prefix}{context}\n\nUser Request: {prompt}"
                    },
                    {
                        "role": "assistant",
                        "content": f"```yaml\n{yaml_content}\n```"
                    }
                ]
            }
            
            examples.append(example)
        
        return examples
    
    def save_jsonl(self, examples: List[Dict], output_file: Path):
        """Save examples in JSONL format."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')
        
        print(f"✅ Saved {len(examples)} examples to {output_file}")
    
    def save_modelfile(self, content: str, output_file: Path):
        """Save Ollama Modelfile format."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content, encoding='utf-8')
        
        lines = content.count('\n')
        print(f"✅ Saved Modelfile with {lines} lines to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Pockitect training data to fine-tuning format"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["ollama", "unsloth", "alpaca", "chatml"],
        default="unsloth",
        help="Output format (default: unsloth)"
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=Path("data/training"),
        help="Training data directory (default: data/training)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: auto-generated based on format)"
    )
    
    args = parser.parse_args()
    
    if not args.training_dir.exists():
        print(f"❌ Training directory does not exist: {args.training_dir}")
        sys.exit(1)
    
    converter = FineTuningConverter(args.training_dir)
    pairs = converter.load_training_pairs()
    
    if not pairs:
        print(f"❌ No training pairs found in {args.training_dir}")
        sys.exit(1)
    
    print(f"📚 Loaded {len(pairs)} training pairs\n")
    
    # Generate output path if not provided
    if args.output is None:
        if args.format == "ollama":
            args.output = Path("data/finetuning/modelfile.txt")
        else:
            args.output = Path(f"data/finetuning/train_{args.format}.jsonl")
    
    # Convert based on format
    if args.format == "ollama":
        content = converter.convert_to_ollama_format(pairs)
        converter.save_modelfile(content, args.output)
        
    elif args.format == "unsloth":
        examples = converter.convert_to_unsloth_format(pairs)
        converter.save_jsonl(examples, args.output)
        
    elif args.format == "alpaca":
        examples = converter.convert_to_alpaca_format(pairs)
        converter.save_jsonl(examples, args.output)
        
    elif args.format == "chatml":
        examples = converter.convert_to_chatml_format(pairs)
        converter.save_jsonl(examples, args.output)
    
    print(f"\n✅ Conversion complete! Format: {args.format}")
    print(f"📁 Output: {args.output}")


if __name__ == "__main__":
    main()
