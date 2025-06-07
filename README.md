# Simple Chat

A command-line interface for interacting with OpenAI-compatible model endpoints, including support for multiple model servers and advanced testing capabilities.

## Features

- **Multi-Model Support**: Connect to various OpenAI-compatible endpoints
- **Rich Terminal UI**: Beautiful markdown rendering with syntax highlighting
- **Server Testing**: Comprehensive testing suite with both console and curses UI modes
- **Configuration Management**: YAML-based server configuration
- **Logging**: Automatic conversation logging with timestamped backups
- **Multi-line Input**: Support for complex prompts and file-based input
- **LaTeX Rendering**: Basic LaTeX-to-text conversion for mathematical content

## Quick Start

1. **Install dependencies**:
   ```bash
   ./install.sh
   ```

2. **Configure your models** (optional):
   Edit `model_servers.yaml` to add your model endpoints

3. **Run the chat interface**:
   ```bash
   python chat_base_v5.py
   ```

4. **Test your model servers**:
   ```bash
   python curses_server_testing.py
   ```

## Commands

### Chat Interface Commands

- `\M` - Enter multi-line mode (end with `<<<` on its own line)
- `\P <file>` - Load and send file contents as prompt
- `\R [file]` - Reset context, optionally saving to file
- `\L <file>` - Load previous log file as context
- `\$` - Show elapsed time and token count
- `\Q` - Graceful shutdown (renames logs)
- `\h`, `\?` - Show help
- `exit`, `quit` - Exit immediately

### Server Testing Commands

```bash
# Test all configured servers with curses UI (default)
python curses_server_testing.py

# Test servers in console mode
python curses_server_testing.py --console

# Test only non-OpenAI servers
python curses_server_testing.py --cels-only

# Run continuous testing with 30-second intervals
python curses_server_testing.py --delay 30

# Use custom configuration file
python curses_server_testing.py --config my_servers.yaml
```

## Configuration

### Model Servers Configuration

Create or edit `model_servers.yaml`:

```yaml
servers:
  # Local model server
  - server: "localhost"
    shortname: "local"
    openai_api_key: "${VLLM_API_KEY}"
    openai_api_base: "http://127.0.0.1:1234/v1"
    openai_model: "my-local-model"

  # OpenAI GPT
  - server: "api.openai.com"
    shortname: "gpt4"
    openai_api_key: "${OPENAI_API_KEY}"
    openai_api_base: "https://api.openai.com/v1"
    openai_model: "gpt-4"
```

### Environment Variables

Set the following environment variables:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export VLLM_API_KEY="your-local-server-key"
```

## Usage Examples

### Basic Chat

```bash
# Start chat with default model
python chat_base_v5.py

# Use specific model
python chat_base_v5.py --model gpt4

# List available models
python chat_base_v5.py --list-models
```

### Multi-line Input

```
You: \M
Entering multi-line mode. End with a line containing only <<<
Please analyze this code:

def hello_world():
    print("Hello, World!")
    
What could be improved?
<<<
```

### File Input

```
You: \P my_code.py
```

### Server Testing

The server testing utility provides both console and curses-based interfaces:

**Curses UI Mode** (default):
- Real-time status updates for all servers
- Color-coded results
- Timing and token usage information
- Interactive controls (q to quit, r to refresh)

**Console Mode**:
- Detailed text output
- Good for logging and automation
- Supports continuous testing with delays

## Dependencies

- Python 3.7+
- openai
- rich
- pylatexenc
- regex
- pyyaml

## Installation

### Using the Install Script

```bash
./install.sh
```

The install script supports:
- Automatic Python version detection
- pip and conda package managers
- Virtual environment setup
- Dependency verification

### Manual Installation

```bash
# Using pip
pip install openai rich pylatexenc regex pyyaml

# Using conda
conda install -c conda-forge openai rich pyyaml
pip install pylatexenc regex  # These may not be available in conda
```

## Files

- `chat_base_v5.py` - Main chat interface
- `curses_server_testing.py` - Server testing utility
- `model_servers.yaml` - Server configuration
- `install.sh` - Installation script
- `prompts.log` - User input log
- `outputs.log` - Assistant response log

## License

This project is open source. See the repository for license details.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.