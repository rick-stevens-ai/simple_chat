#!/usr/bin/env python3
"""
Simple Chat CLI for OpenAI‑compatible endpoints.

Commands
--------
 \\M                – paste a multi‑line prompt, finish with <<< on its own line
 \\P <file>         – load entire file and send as prompt
 \\R [file]         – reset context, optionally saving current context to <file>
 \\L <file>         – load previous output log file as context (after printing this one)
 \\$                – show elapsed time and token count
 \\Q                – graceful shutdown (renames logs)
 \\h, \\?           – show available commands
 exit / quit        – quit immediately (no log rename)

Requirements
------------
 * Python 3.7+ (no `match‑case` so it works on 3.8/3.9 too)
 * pip install openai rich pylatexenc regex
"""

# ------------------------------------------------------------------------------
# 0. Configuration (API Key, Endpoint, Model)
# ------------------------------------------------------------------------------
# Default configuration - will be overridden by YAML settings if available
DEFAULT_API_KEY = "CELS" 
DEFAULT_API_BASE = "http://66.55.67.65:80/v1"
DEFAULT_MODEL = "scout"
YAML_CONFIG_FILE = "model_servers.yaml"

# ------------------------------------------------------------------------------
# Imports
# ------------------------------------------------------------------------------
import os
import sys
import time
import re
import regex
import yaml
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import openai
from rich.console   import Console
from rich.markdown  import Markdown
from rich.syntax    import Syntax
from rich.table     import Table
from rich.panel     import Panel
from pylatexenc.latex2text import LatexNodes2Text

# ------------------------------------------------------------------------------
# 1. Parsing / Display Utilities
# ------------------------------------------------------------------------------
_CODE_LATEX_PATTERN = re.compile(
    r'(?:```[\s\S]*?```)|(?:\$\$.*?\$\$)|(?:\$.*?\$)'
)


def parse_input(input_string: str):
    """Tokenise assistant output into markdown / code / latex chunks."""
    tokens = []
    last_end = 0
    for match in _CODE_LATEX_PATTERN.finditer(input_string):
        start, end = match.span()
        if start > last_end:
            tokens.append({"type": "markdown", "content": input_string[last_end:start]})
        content = match.group()
        if content.startswith("```"):
            tokens.append({"type": "code", "content": content})
        else:
            tokens.append({"type": "latex", "content": content})
        last_end = end
    if last_end < len(input_string):
        tokens.append({"type": "markdown", "content": input_string[last_end:]})
    return tokens


def process_markdown(content: str, console: Console):
    console.print(Markdown(content))


def process_latex(content: str, console: Console):
    if content.startswith("$$"):
        content = content[2:-2]
    elif content.startswith('$'):
        content = content[1:-1]
    console.print(LatexNodes2Text().latex_to_text(content))


def process_code(content: str, console: Console):
    m = re.match(r'```(\w+)?\n', content)
    if m:
        language = m.group(1) or ""
        code = content[m.end():]
        code = code.rstrip('`').rstrip()
    else:
        language = ""
        code = content.strip('`')
    console.print(Syntax(code, lexer=language, line_numbers=False))

# ------------------------------------------------------------------------------
# 2. Logging Utilities
# ------------------------------------------------------------------------------

def rename_logs(prompts_log: str, outputs_log: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        if os.path.exists(prompts_log):
            os.rename(prompts_log, f"prompts_{ts}.log")
        if os.path.exists(outputs_log):
            os.rename(outputs_log, f"outputs_{ts}.log")
    except OSError as e:
        print(f"Warning: Could not rename log files: {e}")


def append_line(path: str, text: str):
    try:
        with open(path, 'a', encoding='utf-8', errors='replace') as f:
            f.write(text + "\n")
    except IOError as e:
        print(f"Warning: Could not write to {path}: {e}")

# ------------------------------------------------------------------------------
# 3. Configuration Loading Functions
# ------------------------------------------------------------------------------

def load_server_configs(config_file: str = None) -> List[Dict[str, Any]]:
    """Load server configurations from YAML file."""
    if config_file is None:
        config_file = YAML_CONFIG_FILE
        
    if not os.path.exists(config_file):
        print(f"Warning: Configuration file {config_file} not found.")
        return []
        
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if config and 'servers' in config and isinstance(config['servers'], list):
                return config['servers']
            else:
                print(f"Warning: No valid server configurations found in {config_file}")
                return []
    except Exception as e:
        print(f"Error loading configuration file {config_file}: {e}")
        return []


def select_server_config(model_name: Optional[str] = None, config_file: str = None) -> Tuple[str, str, str]:
    """
    Select a server configuration based on model name.
    Returns (api_key, api_base, model_name)
    """
    servers = load_server_configs(config_file)
    
    # If no model specified or no configurations found, use defaults
    if not model_name or not servers:
        return DEFAULT_API_KEY, DEFAULT_API_BASE, DEFAULT_MODEL
    
    # Find server with matching model name or shortname
    for server in servers:
        if (server.get('openai_model', '').lower() == model_name.lower() or 
            server.get('server', '').lower() == model_name.lower() or
            server.get('shortname', '').lower() == model_name.lower()):
            
            api_key = server.get('openai_api_key', DEFAULT_API_KEY)
            
            # Handle environment variable in API key
            if api_key.startswith("${") and api_key.endswith("}"):
                env_var = api_key[2:-1]
                api_key = os.environ.get(env_var)
                if not api_key:
                    raise ValueError(f"Environment variable {env_var} not set. Required for {server.get('openai_model')}")
            
            return (
                api_key,
                server.get('openai_api_base', DEFAULT_API_BASE),
                server.get('openai_model', DEFAULT_MODEL)
            )
    # If model not found, return error message and use defaults
    print(f"Warning: Model '{model_name}' not found in configuration. Using default model.")
    return DEFAULT_API_KEY, DEFAULT_API_BASE, DEFAULT_MODEL


def list_available_models(console: Console, config_file: str = None) -> None:
    """Display a table of available models from the YAML configuration."""
    servers = load_server_configs(config_file)
    
    if not servers:
        console.print("[yellow]No models found in configuration file.[/yellow]")
        console.print(f"[cyan]Using default model: {DEFAULT_MODEL}[/cyan]")
        return
        
    table = Table(title="Available Models")
    table.add_column("Model", style="cyan")
    table.add_column("Shortname", style="yellow")
    table.add_column("Server", style="green")
    table.add_column("API Base URL", style="blue")
    
    for server in servers:
        table.add_row(
            server.get('openai_model', 'Unknown'),
            server.get('shortname', 'N/A'),
            server.get('server', 'Unknown'),
            server.get('openai_api_base', 'Unknown')
        )
    console.print(table)

# ------------------------------------------------------------------------------
# 4. Main Chat Logic
# ------------------------------------------------------------------------------

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Simple Chat CLI for OpenAI‑compatible endpoints")
    parser.add_argument("--model", "-m", type=str, help="Model name or shortname to use from configuration")
    parser.add_argument("--list-models", "-l", action="store_true", help="List available models with their shortnames")
    parser.add_argument("--config", "-c", type=str, default="model_servers.yaml", help="Path to model servers configuration file (default: model_servers.yaml)")
    args = parser.parse_args()
    
    console = Console()
    prompts_log  = "prompts.log"
    outputs_log  = "outputs.log"
    
    # Handle --list-models flag
    if args.list_models:
        list_available_models(console, args.config)
        return

    try:
        open(prompts_log, 'w', encoding='utf-8').close()
        open(outputs_log, 'w', encoding='utf-8').close()
    except IOError as e:
        console.print(f"[red]Error creating log files: {e}[/red]")
        sys.exit(1)

    # Select model configuration based on command line argument
    try:
        api_key, api_base, model_name = select_server_config(args.model, args.config)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    
    client = openai.OpenAI(api_key=api_key, base_url=api_base)

    messages = []
    start_time   = time.time()
    total_tokens = 0

    def banner():
        model_display = model_name.split('/')[-1] if '/' in model_name else model_name
        console.print(f"[bold green]Welcome to Simple Chat powered by [cyan]{model_display}[/cyan]![/bold green]")
        console.print(f"[blue]Using API endpoint: {api_base}[/blue]")
        console.print(r"[cyan]\M[/cyan]      – multi‑line prompt     |  [cyan]\P <file>[/cyan] – prompt from file")
        console.print(r"[cyan]\R[/cyan]      – reset & dump          |  [cyan]\L <file>[/cyan] – load log as context")
        console.print(r"[cyan]\$[/cyan]      – stats so far          |  [cyan]\Q[/cyan]      – graceful shutdown")
        console.print(r"[cyan]\h[/cyan], [cyan]\?[/cyan]  – show commands         |  Type [italic]exit[/italic] or [italic]quit[/italic] to leave")
        console.print()


    banner()

    def show_stats():
        elapsed = time.time() - start_time
        console.print(f"[bold blue]Elapsed:[/bold blue] {elapsed:.2f}s    [bold blue]Tokens:[/bold blue] {total_tokens}")
        console.print()  # Add spacing after stats
        
    def show_help():
        console.print("[bold yellow]Available Commands:[/bold yellow]")
        console.print(r"[cyan]\M[/cyan]                – paste a multi‑line prompt, finish with <<< on its own line")
        console.print(r"[cyan]\P <file>[/cyan]         – load entire file and send as prompt")
        console.print(r"[cyan]\R[/cyan] [file]         – reset context, optionally saving current context to <file>")
        console.print(r"[cyan]\L <file>[/cyan]         – load previous output log file as context")
        console.print(r"[cyan]\$[/cyan]                – show elapsed time and token count")
        console.print(r"[cyan]\Q[/cyan]                – graceful shutdown (renames logs)")
        console.print(r"[cyan]\h, \?[/cyan]            – show this help message")
        console.print(r"[italic]exit, quit[/italic]    – exit immediately without renaming logs")
        console.print()  # Add spacing after help display
    
    def reset_context(save_file: Optional[str] = None):
        nonlocal messages, start_time, total_tokens
        if save_file:
            try:
                with open(save_file, 'w', encoding='utf-8', errors='replace') as f:
                    for m in messages:
                        f.write(f"{m['role'].upper()}: {m['content']}\n")
                console.print(f"[green]Context saved to {save_file}[/green]")
            except IOError as e:
                console.print(f"[red]Error saving context to {save_file}: {e}[/red]")
        
        rename_logs(prompts_log, outputs_log)
        try:
            open(prompts_log, 'w', encoding='utf-8').close()
            open(outputs_log, 'w', encoding='utf-8').close()
        except IOError as e:
            console.print(f"[red]Error resetting log files: {e}[/red]")
        
        messages = []
        start_time = time.time()
        total_tokens = 0
        console.print("[bold green]Context reset.[/bold green]")

    def graceful_shutdown():
        show_stats()
        rename_logs(prompts_log, outputs_log)
        console.print("[bold red]Shutting down…[/bold red]")
        sys.exit(0)

    # ------------------- Main REPL -------------------
    while True:
        console.print()  # blank line for spacing
        
        # Method 1: Use Rich to print the prompt, then input() without a prompt
        console.print("[cyan]You:[/cyan]", end=" ")
        sys.stdout.flush()  # Make sure the prompt is visible before the input
        user_input = input().rstrip()
        if user_input.lower() in {"exit", "quit"}:
            console.print("[bold green]Goodbye![/bold green]")
            break

        if user_input.startswith("\\$"):
            show_stats()
            continue
            
        if user_input.startswith("\\h") or user_input.startswith("\\?"):
            show_help()
            continue

        if user_input.startswith("\\Q"):
            graceful_shutdown()

        if user_input.startswith("\\R"):
            parts = user_input.split(maxsplit=1)
            reset_context(parts[1] if len(parts) > 1 else None)
            continue

        if user_input.startswith("\\L "):
            file_to_load = user_input[3:].strip()
            if not file_to_load:
                console.print("[red]Error: Missing filename after \\L command[/red]")
                continue
                
            try:
                with open(file_to_load, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    messages.append({"role": "assistant", "content": content})
                console.print(f"[green]Loaded context from {file_to_load}[/green]")
            except FileNotFoundError:
                console.print(f"[red]File not found: {file_to_load}[/red]")
            except IOError as e:
                console.print(f"[red]Error reading file {file_to_load}: {e}[/red]")
            continue

        if user_input.startswith("\\M"):
            console.print("[yellow]Entering multi‑line mode. End with a line containing only <<<[/yellow]")
            multi_lines = []
            while True:
                try:
                    line = input()
                except KeyboardInterrupt:
                    console.print("[red]Cancelled.[/red]")
                    multi_lines = []
                    break
                if line.strip() == "<<<":
                    break
                multi_lines.append(line)
            user_input = "\n".join(multi_lines).strip()
            if not user_input:
                continue  # nothing to send

        elif user_input.startswith("\\P "):
            file_to_read = user_input[3:].strip()
            if not file_to_read:
                console.print("[red]Error: Missing filename after \\P command[/red]")
                continue
                
            try:
                with open(file_to_read, 'r', encoding='utf-8', errors='replace') as f:
                    user_input = f.read()
                    if not user_input.strip():
                        console.print(f"[yellow]Warning: File {file_to_read} is empty[/yellow]")
                        continue
            except FileNotFoundError:
                console.print(f"[red]File not found: {file_to_read}[/red]")
                continue
            except IOError as e:
                console.print(f"[red]Error reading file {file_to_read}: {e}[/red]")
                continue

        # ---- Send to LLM ----
        append_line(prompts_log, user_input)
        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(model=model_name, messages=messages)
        except Exception as e:
            console.print(f"[red]API error: {e}[/red]")
            messages.pop()  # remove last user message
            continue

        assistant_msg = response.choices[0].message.content
        append_line(outputs_log, assistant_msg)

        try:
            if response.usage is not None:
                total_tokens += response.usage.total_tokens or 0
        except (AttributeError, TypeError):
            # Handle case where usage information is unavailable
            pass

        messages.append({"role": "assistant", "content": assistant_msg})

        # ---- Render nicely ----
        for t in parse_input(assistant_msg):
            if t["type"] == "markdown":
                process_markdown(t["content"], console)
            elif t["type"] == "latex":
                process_latex(t["content"], console)
            elif t["type"] == "code":
                process_code(t["content"], console)

# ------------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Bye!")
