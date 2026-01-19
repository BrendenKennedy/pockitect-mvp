#!/usr/bin/env python3
"""
Synthetic training data generator for Pockitect.
Uses GPT-4/Claude to generate diverse prompt/YAML pairs automatically.

Usage:
    python tools/generate_synthetic_training_data.py --count 50 --provider openai
    python tools/generate_synthetic_training_data.py --count 100 --provider anthropic
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Try to import API clients
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from storage import create_empty_blueprint


class SyntheticDataGenerator:
    def __init__(
        self,
        provider: str = "openai",
        model: str = None,
        api_key: str = None
    ):
        self.provider = provider.lower()
        
        # Set default models
        if model is None:
            if self.provider == "openai":
                model = "gpt-4-turbo-preview"
            elif self.provider == "anthropic":
                model = "claude-3-5-sonnet-20241022"
            else:
                raise ValueError(f"Unknown provider: {provider}")
        
        self.model = model
        
        if self.provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "OpenAI package not installed. Install with: pip install openai"
                )
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.client = OpenAI(api_key=api_key)
            
        elif self.provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError(
                    "Anthropic package not installed. Install with: pip install anthropic"
                )
            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'anthropic'")
    
    def get_schema_template(self) -> str:
        """Get the YAML schema template based on actual training data format."""
        example = create_empty_blueprint("example-project")
        # Convert to the training format (simplified)
        return json.dumps({
            "project": {
                "name": "string (slug-friendly, lowercase with hyphens)",
                "description": "string",
                "region": "string (AWS region code like us-east-1, eu-west-1)",
                "owner": "string"
            },
            "network": {
                "vpc_mode": "default | new | existing",
                "vpc_cidr": "string | null (e.g., 10.0.0.0/16)",
                "subnet_type": "public | private",
                "rules": [
                    {
                        "port": "number (e.g., 22, 80, 443)",
                        "protocol": "tcp | udp",
                        "cidr": "string (IP range like 0.0.0.0/0 or 10.0.0.0/8)",
                        "description": "string (e.g., SSH, HTTP, HTTPS)"
                    }
                ]
            },
            "compute": {
                "instance_type": "string (e.g., t3.micro, t3.small, t3.medium, t3.large)",
                "image_id": "string | null",
                "image_name": "string | null (e.g., ubuntu-22.04, amazon-linux-2)",
                "user_data": "string (bash script starting with #!/bin/bash or empty string)"
            },
            "data": {
                "db": {
                    "engine": "postgres | mysql | mariadb",
                    "instance_class": "string (e.g., db.t3.micro, db.t3.small)",
                    "allocated_storage_gb": "number (e.g., 20, 50, 100)",
                    "username": "string"
                } | None,
                "s3_bucket": {
                    "name": "string (lowercase, no spaces)"
                } | None
            },
            "security": {
                "key_pair": {
                    "mode": "generate | existing",
                    "name": "string"
                },
                "certificate": {
                    "mode": "skip | request"
                },
                "iam_role": {
                    "enabled": "boolean",
                    "role_name": "string"
                }
            }
        }, indent=2)
    
    def get_existing_examples(self, training_dir: Path) -> List[str]:
        """Get prompts from existing training examples for context."""
        examples = []
        for prompt_file in sorted(training_dir.glob("*.prompt.txt")):
            try:
                prompt = prompt_file.read_text(encoding="utf-8").strip()
                examples.append(prompt[:200])  # First 200 chars
            except Exception:
                pass
        return examples[:5]  # Return first 5 as context
    
    def generate_training_example(
        self,
        scenario_type: Optional[str] = None,
        existing_examples: List[str] = None
    ) -> Dict:
        """Generate a single training example."""
        
        schema = self.get_schema_template()
        
        existing_context = ""
        if existing_examples:
            existing_context = "\n\nExample prompts (vary your style):\n" + "\n".join(
                f"- {ex}" for ex in existing_examples
            )
        
        system_prompt = f"""You are an expert AWS infrastructure architect. Generate realistic training examples for a tool that converts natural language to AWS infrastructure JSON blueprints.

YAML Schema (return as JSON):
{schema}

Guidelines:
- Make prompts natural and varied (different phrasings, styles, verbosity)
- Cover diverse scenarios: blogs, APIs, databases, static sites, microservices, Docker hosts, data pipelines, etc.
- Use realistic AWS regions (us-east-1, us-west-2, eu-west-1, ap-southeast-1, etc.)
- Use realistic instance types (t3.micro, t3.small, t3.medium, t3.large)
- Include edge cases: restricted IPs, custom VPCs, no database, S3-only, etc.
- Ensure JSON is valid and matches the schema exactly
- Vary complexity (simple single-service to complex multi-component)
- Use natural language variations: "I need", "Set up", "Create", "Build", "Deploy", etc.
- Include specific requirements naturally (ports, storage sizes, regions)
{existing_context}

Return ONLY a JSON object with this exact structure:
{{
  "prompt": "natural language description (2-8 sentences, varied style)",
  "yaml": {{...blueprint JSON matching schema...}}
}}

The "yaml" field should be valid JSON matching the schema above."""

        user_prompt = f"""Generate a realistic AWS infrastructure training example.

Scenario type: {scenario_type or "random (choose from: blog, api-server, static-website, database-backend, microservice, docker-host, full-stack, data-pipeline, game-server, monitoring-stack, caching-layer, queue-worker, or create a unique scenario)"}

Make it diverse and realistic. Vary the phrasing and style from previous examples. Include specific technical details naturally."""

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.9  # High temperature for diversity
                )
                result = json.loads(response.choices[0].message.content)
                
            else:  # anthropic
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.9
                )
                content = response.content[0].text
                
                # Extract JSON from markdown if needed
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                result = json.loads(content)
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON decode error: {e}")
            raise
        except Exception as e:
            print(f"  ⚠️  API error: {e}")
            raise
    
    def generate_batch(
        self,
        count: int,
        output_dir: Path,
        scenario_types: Optional[List[str]] = None,
        delay: float = 0.5
    ) -> List[Dict]:
        """Generate multiple training examples."""
        
        if scenario_types is None:
            scenario_types = [
                "blog", "api-server", "static-website", "database-backend",
                "microservice", "docker-host", "full-stack", "data-pipeline",
                "game-server", "monitoring-stack", "caching-layer", "queue-worker",
                "e-commerce-backend", "ml-training-server", "file-storage-service",
                "websocket-server", "batch-processing", "ci-cd-runner"
            ]
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get existing examples for context
        existing_examples = self.get_existing_examples(output_dir)
        
        generated = []
        failed = 0
        
        print(f"\n🚀 Generating {count} training examples using {self.provider} ({self.model})...")
        print(f"📁 Output directory: {output_dir}\n")
        
        for i in range(count):
            scenario = scenario_types[i % len(scenario_types)]
            
            try:
                example = self.generate_training_example(
                    scenario_type=scenario,
                    existing_examples=existing_examples if i < 10 else None  # Only use context for first 10
                )
                
                # Validate structure
                if "prompt" not in example or "yaml" not in example:
                    print(f"  ✗ Example {i+1}: Missing required fields (prompt/yaml)")
                    failed += 1
                    continue
                
                # Basic validation
                yaml_data = example["yaml"]
                if not isinstance(yaml_data, dict):
                    print(f"  ✗ Example {i+1}: YAML is not a dict")
                    failed += 1
                    continue
                
                if "project" not in yaml_data or "network" not in yaml_data:
                    print(f"  ✗ Example {i+1}: Missing required sections")
                    failed += 1
                    continue
                
                # Save in your existing format
                existing_files = list(output_dir.glob("*.json"))
                num = len(existing_files) + 1
                name = f"{num:03d}-{scenario}"
                
                prompt_file = output_dir / f"{name}.prompt.txt"
                json_file = output_dir / f"{name}.json"
                
                prompt_file.write_text(example["prompt"], encoding="utf-8")
                json_file.write_text(
                    json.dumps(yaml_data, indent=2),
                    encoding="utf-8"
                )
                
                generated.append(example)
                print(f"  ✓ [{i+1}/{count}] Generated {name}")
                
                # Add to existing examples for context
                if len(existing_examples) < 10:
                    existing_examples.append(example["prompt"][:200])
                
                # Rate limiting
                if delay > 0:
                    time.sleep(delay)
                
            except KeyboardInterrupt:
                print(f"\n\n⚠️  Interrupted by user. Generated {len(generated)} examples so far.")
                break
            except Exception as e:
                print(f"  ✗ Example {i+1}: Error - {e}")
                failed += 1
                continue
        
        print(f"\n✅ Successfully generated {len(generated)}/{count} examples")
        if failed > 0:
            print(f"⚠️  Failed to generate {failed} examples")
        
        return generated


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic training data for Pockitect AI model"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of examples to generate (default: 50)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "anthropic"],
        default="openai",
        help="API provider to use (default: openai)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: gpt-4-turbo-preview for OpenAI, claude-3-5-sonnet-20241022 for Anthropic)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/training"),
        help="Output directory for training data (default: data/training)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between API calls in seconds (default: 0.5)"
    )
    
    args = parser.parse_args()
    
    try:
        generator = SyntheticDataGenerator(
            provider=args.provider,
            model=args.model
        )
        
        generator.generate_batch(
            count=args.count,
            output_dir=args.output_dir,
            delay=args.delay
        )
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
