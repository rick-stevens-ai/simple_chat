#!/usr/bin/env python3
import os
import sys
import yaml
import openai
import time
import argparse
import asyncio
import io
import curses
import textwrap
from datetime import datetime
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError, AuthenticationError
# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Model-specific parameters dictionary
MODEL_PARAMS = {
    # OpenAI models
    "o3": {"max_completion_tokens": 100},  # Use max_completion_tokens for o3
    "o4-mini": {"max_completion_tokens": 150},  # Increased tokens for o4-mini
    "gpt-4.1": {"max_completion_tokens": 50},  # Use max_completion_tokens for gpt-4.1
    
    # CELS models 
    "scout": {"max_completion_tokens": 50},  # Scout model
    "Qwen": {"max_completion_tokens": 50},  # Qwen model
    "meta-llama/Llama-3.3-70B-Instruct": {"max_completion_tokens": 50},  # Llama 3.3 70B model
}

# Server-specific curses colors
SERVER_COLORS = {
    "scout": 1,    # Orange-like
    "qwen": 2,     # Purple-like
    "llama": 3,    # Blue
    "gpt41": 4,    # Green
    "o3": 5,       # Red-Orange
    "o4mini": 6,   # Yellow
    # Default for any other servers
    "default": 7   # White
}

# Curses color pairs
CURSES_COLOR_PAIRS = {
    "normal": 1,
    "success": 2,
    "error": 3,
    "header": 4,
    "status": 5,
    "time": 6
}

class CursesUI:
    """Manages the curses-based UI for server testing"""
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.server_windows = {}
        self.header_win = None
        self.footer_win = None
        self.max_y, self.max_x = stdscr.getmaxyx()
        self.setup_colors()
        
    def setup_colors(self):
        """Initialize color pairs for the UI"""
        curses.start_color()
        curses.use_default_colors()
        
        # Initialize color pairs
        curses.init_pair(CURSES_COLOR_PAIRS["normal"], curses.COLOR_WHITE, -1)
        curses.init_pair(CURSES_COLOR_PAIRS["success"], curses.COLOR_GREEN, -1)
        curses.init_pair(CURSES_COLOR_PAIRS["error"], curses.COLOR_RED, -1)
        curses.init_pair(CURSES_COLOR_PAIRS["header"], curses.COLOR_CYAN, -1)
        curses.init_pair(CURSES_COLOR_PAIRS["status"], curses.COLOR_YELLOW, -1)
        curses.init_pair(CURSES_COLOR_PAIRS["time"], curses.COLOR_BLUE, -1)
        
        # Server-specific colors
        curses.init_pair(SERVER_COLORS["scout"], curses.COLOR_MAGENTA, -1)
        curses.init_pair(SERVER_COLORS["qwen"], curses.COLOR_CYAN, -1)
        curses.init_pair(SERVER_COLORS["llama"], curses.COLOR_BLUE, -1)
        curses.init_pair(SERVER_COLORS["gpt41"], curses.COLOR_GREEN, -1)
        curses.init_pair(SERVER_COLORS["o3"], curses.COLOR_RED, -1)
        curses.init_pair(SERVER_COLORS["o4mini"], curses.COLOR_YELLOW, -1)
        curses.init_pair(SERVER_COLORS["default"], curses.COLOR_WHITE, -1)
        
    def setup_windows(self, servers):
        """Create windows for each server and header/footer"""
        # Clear everything
        self.stdscr.clear()
        self.server_windows = {}
        
        # Get current terminal dimensions
        self.max_y, self.max_x = self.stdscr.getmaxyx()
        
        # Create header window (3 lines at top)
        header_height = 3
        self.header_win = curses.newwin(header_height, self.max_x, 0, 0)
        
        # Create footer window (3 lines at bottom)
        footer_height = 3
        self.footer_win = curses.newwin(footer_height, self.max_x, self.max_y - footer_height, 0)
        
        # Calculate server window layout
        num_servers = len(servers)
        available_height = self.max_y - header_height - footer_height
        
        # Determine grid layout based on number of servers
        if num_servers <= 2:
            rows, cols = 1, num_servers
        elif num_servers <= 4:
            rows, cols = 2, 2
        elif num_servers <= 6:
            rows, cols = 2, 3
        elif num_servers <= 9:
            rows, cols = 3, 3
        else:
            # More complex layout for many servers
            rows = (num_servers + 2) // 3
            cols = 3
            
        # Calculate window dimensions
        win_height = available_height // rows
        win_width = self.max_x // cols
        
        # Create windows for each server
        for i, server in enumerate(servers):
            shortname = server.get('shortname')
            model_name = server.get('openai_model')
            api_base = server.get('openai_api_base', 'https://api.openai.com/v1')
            
            # Calculate position
            row = i // cols
            col = i % cols
            
            y = header_height + (row * win_height)
            x = col * win_width
            
            # Create window
            win = curses.newwin(win_height, win_width, y, x)
            win.scrollok(True)
            
            # Setup server window info
            self.server_windows[shortname] = {
                'window': win,
                'model': model_name,
                'api_base': api_base,
                'server': server.get('server', 'Unknown'),
                'status': 'Waiting',
                'color': SERVER_COLORS.get(shortname, SERVER_COLORS["default"]),
                'lines': [],  # Store lines of output
                'start_time': None,
                'end_time': None,
                'response_time': None,
                'tokens': None,
                'response_ok': False
            }
            
            # Draw initial window
            self.update_server_window(shortname)
            
        # Update header and footer
        self.update_header()
        self.update_footer("Ready to start tests...")
        
        # Refresh the screen
        self.stdscr.refresh()
        
    def update_header(self, iteration=0):
        """Update the header with test information"""
        if not self.header_win:
            return
            
        self.header_win.clear()
        self.header_win.box()
        
        # Add title
        title = "MODEL SERVER TESTING"
        if iteration > 0:
            title += f" - ITERATION {iteration}"
            
        x = (self.max_x - len(title)) // 2
        self.header_win.addstr(1, x, title, curses.color_pair(CURSES_COLOR_PAIRS["header"]) | curses.A_BOLD)
        
        # Refresh the header
        self.header_win.refresh()
        
    def update_footer(self, message, success=None, countdown=False):
        """Update the footer with status message, optionally as countdown"""
        if not self.footer_win:
            return
            
        self.footer_win.clear()
        self.footer_win.box()
        
        # Determine color based on message type
        color = curses.color_pair(CURSES_COLOR_PAIRS["normal"])
        
        # Use different colors based on message type
        if countdown:
            color = curses.color_pair(CURSES_COLOR_PAIRS["time"]) | curses.A_BOLD
        elif success is not None:
            color = curses.color_pair(
                CURSES_COLOR_PAIRS["success"] if success else CURSES_COLOR_PAIRS["error"]
            )
            
        # Add message
        timestamp = datetime.now().strftime("%H:%M:%S")
        footer_text = f"[{timestamp}] {message}"
        self.footer_win.addstr(1, 2, footer_text, color | curses.A_BOLD)
        
        # Add help text
        help_text = "Press 'q' to quit, 'r' to refresh"
        x = self.max_x - len(help_text) - 3
        if x > 0:
            self.footer_win.addstr(1, x, help_text)
            
        # Refresh the footer
        self.footer_win.refresh()
        
    def add_server_message(self, shortname, message, is_error=False):
        """Add a message to a server's window"""
        if shortname not in self.server_windows:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        server_info = self.server_windows[shortname]
        
        # Add message to lines buffer
        server_info['lines'].append({
            'timestamp': timestamp,
            'message': message,
            'is_error': is_error
        })
        
        # Only keep last 20 messages
        if len(server_info['lines']) > 20:
            server_info['lines'] = server_info['lines'][-20:]
            
        # Update the window
        self.update_server_window(shortname)
        
    def update_server_status(self, shortname, status):
        """Update a server's status"""
        if shortname not in self.server_windows:
            return
            
        server_info = self.server_windows[shortname]
        old_status = server_info['status']
        server_info['status'] = status
        
        # Set timestamps for start and end
        if old_status == 'Waiting' and status == 'Running':
            server_info['start_time'] = datetime.now()
        elif status in ['Success', 'Failed'] and server_info['start_time']:
            server_info['end_time'] = datetime.now()
            
        # Update the window
        self.update_server_window(shortname)
        
    def update_server_window(self, shortname):
        """Redraw a server's window with current information"""
        if shortname not in self.server_windows:
            return
            
        server_info = self.server_windows[shortname]
        win = server_info['window']
        
        # Clear window
        win.clear()
        
        # Draw box and title
        win.box()
        # Include more info in the title: shortname, model, and server
        title = f" {shortname} "
        max_y, max_x = win.getmaxyx()
        title_x = (max_x - len(title)) // 2
        if title_x > 0:
            win.addstr(0, title_x, title, curses.color_pair(server_info['color']) | curses.A_BOLD)
            
        # Show host/endpoint in the top line
        server_info_text = f" {server_info['server']} | {server_info['api_base']} "
        if len(server_info_text) > max_x - 4:  # Truncate if too long
            server_info_text = server_info_text[:max_x-7] + "..."
        win.addstr(1, 2, server_info_text, curses.A_DIM)
        
        # Add status with more info (model name + status)
        status_color = curses.color_pair(CURSES_COLOR_PAIRS["normal"])
        if server_info['status'] == 'Success':
            status_color = curses.color_pair(CURSES_COLOR_PAIRS["success"])
        elif server_info['status'] == 'Failed':
            status_color = curses.color_pair(CURSES_COLOR_PAIRS["error"])
        elif server_info['status'] == 'Running':
            status_color = curses.color_pair(CURSES_COLOR_PAIRS["status"])
            
        # Status line with model name
        win.addstr(2, 2, f"Model: {server_info['model']}", curses.A_DIM)
        win.addstr(3, 2, f"Status: {server_info['status']}", status_color | curses.A_BOLD)
        
        # Add timing information in a compact format
        if server_info['start_time']:
            # Timing row
            start_str = server_info['start_time'].strftime("%H:%M:%S")
            timing_line = f"Started: {start_str}"
            
            if server_info['end_time']:
                duration = (server_info['end_time'] - server_info['start_time']).total_seconds()
                timing_line += f" | Time: {duration:.2f}s"
                
            win.addstr(4, 2, timing_line)
            
            # Response info row
            if server_info['response_ok']:
                win.addstr(5, 2, "Response: OK", curses.color_pair(CURSES_COLOR_PAIRS["success"]))
                if server_info['tokens']:
                    token_info = f"Tokens: {server_info['tokens']}"
                    win.addstr(5, max_x - len(token_info) - 2, token_info)
                
        # Display messages (starting from a lower position)
        y = 6
        for i, line in enumerate(reversed(server_info['lines'])):
            if y + i >= max_y - 1:  # Prevent writing outside window
                break
                
            # Format the message
            msg_color = curses.color_pair(
                CURSES_COLOR_PAIRS["error"] if line['is_error'] else CURSES_COLOR_PAIRS["normal"]
            )
            
            # Add timestamp
            time_color = curses.color_pair(CURSES_COLOR_PAIRS["time"])
            win.addstr(y + i, 1, line['timestamp'], time_color)
            
            # Add message, wrapped if needed
            max_msg_width = max_x - 11  # Allow for timestamp and padding
            if len(line['message']) > max_msg_width:
                msg = line['message'][:max_msg_width-3] + "..."
            else:
                msg = line['message']
                
            win.addstr(y + i, 10, msg, msg_color)
            
        # Refresh window
        win.refresh()
        
    def handle_resize(self, servers):
        """Handle terminal resize event"""
        # Get new dimensions
        self.stdscr.clear()
        curses.endwin()
        self.stdscr = curses.initscr()
        self.setup_windows(servers)
        
    def check_input(self):
        """Check for keyboard input and handle it"""
        # Set timeout for getch to make it non-blocking
        self.stdscr.timeout(100)
        try:
            key = self.stdscr.getch()
            if key == ord('q'):  # Quit
                return "quit"
            elif key == ord('r'):  # Refresh
                return "refresh"
            elif key == curses.KEY_RESIZE:  # Window resize
                return "resize"
        except:
            pass
        return None

def is_openai_server(server):
    """Check if a server is an OpenAI server based on the API base URL"""
    api_base = server.get('openai_api_base', '')
    return 'api.openai.com' in api_base

def filter_servers(servers, cels_only=False):
    """Filter servers based on command-line options"""
    if cels_only:
        return [server for server in servers if not is_openai_server(server)]
    return servers

def load_server_config(config_file="model_servers.yaml"):
    """Load server configurations from YAML file"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config.get('servers', [])
    except Exception as e:
        print(f"Error loading configuration from {config_file}: {str(e)}")
        return []

async def test_openai_endpoint_curses(ui, model_name, api_base, api_key, shortname):
    """Test a model endpoint and update the curses UI"""
    # Update status to running
    ui.update_server_status(shortname, "Running")
    ui.add_server_message(shortname, "Starting test...")
    
    try:
        # Get API key from parameter or environment
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                ui.add_server_message(shortname, "Error: OPENAI_API_KEY environment variable not set", is_error=True)
                ui.update_server_status(shortname, "Failed")
                return False
            
        # Handle variable substitution in API key
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]  # Remove ${ and }
            api_key = os.environ.get(env_var)
            if not api_key:
                ui.add_server_message(shortname, f"Error: Environment variable {env_var} not set", is_error=True)
                ui.update_server_status(shortname, "Failed")
                return False

        # Create client with proper configuration
        ui.add_server_message(shortname, "Creating OpenAI client...")
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base
        )

        # Send a simple test request with model-specific parameters
        params = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": "What is 2+2? Please provide a short, direct answer."}
            ]
        }
        
        # Add model-specific parameters from the dictionary
        # Add model-specific parameters from the dictionary
        if model_name in MODEL_PARAMS:
            params.update(MODEL_PARAMS[model_name])
            ui.add_server_message(shortname, f"Parameters: {MODEL_PARAMS[model_name]}")
        
        # Make the API call
        start_time = datetime.now()
        ui.add_server_message(shortname, "Sending request...")
        try:
            # Use async/await to allow other tests to run concurrently
            response = await asyncio.to_thread(client.chat.completions.create, **params)
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
        except AuthenticationError:
            ui.add_server_message(shortname, "Authentication error: Invalid API key", is_error=True)
            ui.update_server_status(shortname, "Failed")
            return False

        # Check if we got a valid response
        if response and response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            ui.add_server_message(shortname, f"Response received in {response_time:.2f}s")
            
            # Update server window with timing and token info
            server_info = ui.server_windows.get(shortname)
            if server_info:
                server_info['response_time'] = response_time
                if hasattr(response, 'usage'):
                    server_info['tokens'] = response.usage.total_tokens
                server_info['response_ok'] = bool(content)
                
            # Only log minimal response info, not the actual content
            if not content:
                ui.add_server_message(shortname, "Response: EMPTY (model connected but returned no content)", is_error=True)
            else:
                ui.add_server_message(shortname, "Response: OK (content received)")
                
            # Log token usage if available
            if hasattr(response, 'usage'):
                tokens_info = f"Tokens: {response.usage.total_tokens} (prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens})"
                ui.add_server_message(shortname, tokens_info)
                
            ui.update_server_status(shortname, "Success")
            return True
        else:
            ui.add_server_message(shortname, "Error: No valid response received", is_error=True)
            ui.update_server_status(shortname, "Failed")
            return False
            
    except RateLimitError as e:
        ui.add_server_message(shortname, f"Rate limit exceeded: {str(e)}", is_error=True)
        ui.update_server_status(shortname, "Failed")
        return False
    except APIConnectionError as e:
        ui.add_server_message(shortname, f"Connection error: {str(e)}", is_error=True)
        ui.update_server_status(shortname, "Failed")
        return False
    except APITimeoutError as e:
        ui.add_server_message(shortname, f"Timeout error: {str(e)}", is_error=True)
        ui.update_server_status(shortname, "Failed")
        return False
    except APIError as e:
        ui.add_server_message(shortname, f"OpenAI API Error: {str(e)}", is_error=True)
        ui.update_server_status(shortname, "Failed")
        return False
    except Exception as e:
        ui.add_server_message(shortname, f"Unexpected error: {str(e)}", is_error=True)
        ui.update_server_status(shortname, "Failed")
        return False

async def test_openai_endpoint(model_name: str, api_base: str = "https://api.openai.com/v1", api_key=None, shortname=None):
    """Test a specific OpenAI model endpoint asynchronously"""
    try:
        # Get API key from parameter or environment
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                print("Error: OPENAI_API_KEY environment variable not set")
                return False
            
        # Handle variable substitution in API key
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]  # Remove ${ and }
            api_key = os.environ.get(env_var)
            if not api_key:
                print(f"Error: Environment variable {env_var} not set")
                return False

        # Create client with proper configuration
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base
        )

        # Send a simple test request with model-specific parameters
        params = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": "What is 2+2? Please provide a short, direct answer."}
            ]
        }
        
        # Add model-specific parameters from the dictionary
        if model_name in MODEL_PARAMS:
            params.update(MODEL_PARAMS[model_name])
        
        # Catch authentication errors before making the API call
        try:
            # Use async/await to allow other tests to run concurrently
            response = await asyncio.to_thread(client.chat.completions.create, **params)
        except AuthenticationError:
            print(f"[{BOLD}{shortname or model_name}{RESET}] Authentication error: Invalid API key")
            return False

        # Check if we got a valid response
        # Check if we got a valid response
        if response and response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            print(f"[{BOLD}{shortname or model_name}{RESET}] Success: Endpoint responded")
            if content:
                print(f"[{BOLD}{shortname or model_name}{RESET}] Response: {content}")
            else:
                print(f"[{BOLD}{shortname or model_name}{RESET}] Response: EMPTY (model connected but returned no content)")
            if hasattr(response, 'usage'):
                print(f"[{BOLD}{shortname or model_name}{RESET}] Usage: {response.usage}")
            return True
        else:
            print(f"[{BOLD}{shortname or model_name}{RESET}] Error: No valid response received")
            return False
    except RateLimitError as e:
        print(f"[{BOLD}{shortname or model_name}{RESET}] Rate limit exceeded: {str(e)}")
        return False
    except APIConnectionError as e:
        print(f"[{BOLD}{shortname or model_name}{RESET}] Connection error: {str(e)}")
        return False
    except APITimeoutError as e:
        print(f"[{BOLD}{shortname or model_name}{RESET}] Timeout error: {str(e)}")
        return False
    except APIError as e:
        print(f"[{BOLD}{shortname or model_name}{RESET}] OpenAI API Error: {str(e)}")
        return False
    except Exception as e:
        print(f"[{BOLD}{shortname or model_name}{RESET}] Unexpected error: {str(e)}")
        return False
def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test OpenAI-compatible model server endpoints")
    parser.add_argument(
        "--delay", 
        type=int, 
        default=0, 
        help="Delay in seconds between test runs (0 for single run)"
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Run in console mode instead of curses UI"
    )
    parser.add_argument(
        "--cels-only",
        action="store_true",
        help="Test only non-OpenAI endpoints (e.g., CELS servers)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="model_servers.yaml",
        help="Path to model_servers.yaml file (default: model_servers.yaml)"
    )
    return parser.parse_args()

async def test_server_curses(ui, server):
    """Run a test for a single server using the curses UI"""
    model_name = server.get('openai_model')
    api_base = server.get('openai_api_base')
    api_key = server.get('openai_api_key')
    shortname = server.get('shortname', model_name)
    
    # Update UI with server info
    ui.add_server_message(shortname, f"API Base: {api_base}")
    
    # Run the test
    success = await test_openai_endpoint_curses(ui, model_name, api_base, api_key, shortname)
    
    return success

async def test_server(server):
    """Run a test for a single server"""
    model_name = server.get('openai_model')
    api_base = server.get('openai_api_base')
    api_key = server.get('openai_api_key')
    shortname = server.get('shortname', model_name)
    
    # Create a distinctive header for this server test
    server_header = f"\n{'=' * 60}\n{BOLD}{CYAN}SERVER: {shortname} ({model_name}){RESET}\n{'-' * 60}"
    print(server_header)
    print(f"[{BOLD}{shortname}{RESET}] API Base: {api_base}")
    
    # Run the test for this server
    success = await test_openai_endpoint(model_name, api_base, api_key, shortname)
    
    # Display status with color
    status_color = GREEN if success else RED
    status_text = "SUCCESS" if success else "FAILURE"
    print(f"[{BOLD}{shortname}{RESET}] Status: {status_color}{status_text}{RESET}")
    
    # Close the server output section
    print(f"{'-' * 60}")
    
    return success

async def run_tests_curses(ui, servers, iteration=0):
    """Run tests on all configured servers in parallel with curses UI"""
    # Update header with iteration
    ui.update_header(iteration)
    ui.update_footer("Starting tests on all servers...")
    
    # Run all tests concurrently
    results = await asyncio.gather(
        *[test_server_curses(ui, server) for server in servers],
        return_exceptions=False
    )
    
    # Check if all tests were successful
    all_success = all(results)
    
    # Update footer with summary
    if all_success:
        ui.update_footer("All tests completed successfully!", success=True)
    else:
        ui.update_footer("Some tests failed.", success=False)
        
    return all_success

async def run_tests(servers):
    """Run tests on all configured servers in parallel"""
    print(f"\n{YELLOW}TESTING ALL MODEL SERVER ENDPOINTS{RESET}")
    print(f"{YELLOW}Started at: {datetime.now()}{RESET}")
    print(f"{YELLOW}{'=' * 60}{RESET}")

    # Run all tests concurrently
    results = await asyncio.gather(
        *[test_server(server) for server in servers],
        return_exceptions=False
    )
    
    # Check if all tests were successful
    all_success = all(results)
    
    return all_success
async def main_curses(stdscr):
    """Main function for curses mode"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Load server configurations from YAML
    servers = load_server_config(args.config)
    
    # Filter servers based on command-line options
    servers = filter_servers(servers, args.cels_only)
    
    # If no servers loaded, use default test configurations
    if not servers:
        default_servers = [
            {"shortname": "gpt41", "openai_model": "gpt-4.1", "openai_api_base": "https://api.openai.com/v1", "openai_api_key": "${OPENAI_API_KEY}"},
            {"shortname": "o3", "openai_model": "o3", "openai_api_base": "https://api.openai.com/v1", "openai_api_key": "${OPENAI_API_KEY}"},
            {"shortname": "o4mini", "openai_model": "o4-mini", "openai_api_base": "https://api.openai.com/v1", "openai_api_key": "${OPENAI_API_KEY}"}
        ]
        
        # Filter default servers if cels-only mode is enabled
        servers = filter_servers(default_servers, args.cels_only)
        
        # If still no servers after filtering, warn user
        if not servers and args.cels_only:
            print("Warning: No non-OpenAI servers found and --cels-only specified.")
            print("No servers to test. Exiting.")
            return
    
    # Initialize curses
    curses.curs_set(0)  # Hide cursor
    stdscr.clear()
    
    # Create UI object
    ui = CursesUI(stdscr)
    ui.setup_windows(servers)
    
    # Main testing loop
    iteration = 1
    running = True
    test_completed = False
    
    while running:
        # Check for user input
        cmd = ui.check_input()
        if cmd == "quit":
            running = False
        elif cmd == "refresh":
            ui.setup_windows(servers)
        elif cmd == "resize":
            ui.handle_resize(servers)
        
        # Run tests if not already running
        if not test_completed:
            # Run tests once
            await run_tests_curses(ui, servers, iteration)
            test_completed = True
            
            # If we're doing multiple runs with a delay
            # If we're doing multiple runs with a delay
            if args.delay > 0:
                # Display initial waiting message
                ui.update_footer(f"Waiting {args.delay} seconds before next test run...", countdown=True)
                
                # Wait for the delay, but check for user input during this time
                wait_start = time.time()
                while time.time() - wait_start < args.delay:
                    # Calculate remaining time and update footer with countdown
                    elapsed = time.time() - wait_start
                    remaining = args.delay - elapsed
                    
                    # Create a more visual countdown message with progress indicator
                    percent_done = int((elapsed / args.delay) * 100)
                    progress_width = 20  # Width of progress bar
                    chars_filled = int(progress_width * percent_done / 100)
                    
                    # Build progress bar
                    progress_bar = "[" + "=" * chars_filled + " " * (progress_width - chars_filled) + "]"
                    
                    # Update countdown with progress
                    message = f"NEXT TEST: {int(remaining)}s remaining {progress_bar} {percent_done}%"
                    ui.update_footer(message, countdown=True)
                    
                    # Check for user input
                    cmd = ui.check_input()
                    if cmd == "quit":
                        running = False
                        break
                    elif cmd == "refresh":
                        ui.setup_windows(servers)
                    elif cmd == "resize":
                        ui.handle_resize(servers)
                    
                    # Brief sleep to prevent CPU hogging but update display frequently
                    await asyncio.sleep(0.1)
                
                # If still running, increment iteration and reset test_completed
                if running and args.delay > 0:
                    iteration += 1
                    test_completed = False
    # Final message before exiting
    ui.update_footer("Exiting test runner...", success=None)
    time.sleep(0.5)  # Brief pause to show the message

async def main_async():
    """Original async entry point for console mode"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Load server configurations from YAML
    servers = load_server_config(args.config)
    
    # Filter servers based on command-line options
    servers = filter_servers(servers, args.cels_only)
    
    # If no servers loaded, use default test configurations
    if not servers:
        print("Warning: No server configurations loaded from YAML. Using defaults.")
        default_servers = [
            {"shortname": "gpt41", "openai_model": "gpt-4.1", "openai_api_base": "https://api.openai.com/v1", "openai_api_key": "${OPENAI_API_KEY}"},
            {"shortname": "o3", "openai_model": "o3", "openai_api_base": "https://api.openai.com/v1", "openai_api_key": "${OPENAI_API_KEY}"},
            {"shortname": "o4mini", "openai_model": "o4-mini", "openai_api_base": "https://api.openai.com/v1", "openai_api_key": "${OPENAI_API_KEY}"}
        ]
        
        # Filter default servers if cels-only mode is enabled
        servers = filter_servers(default_servers, args.cels_only)
        
        # If still no servers after filtering, warn user
        if not servers and args.cels_only:
            print("Warning: No non-OpenAI servers found and --cels-only specified.")
            print("No servers to test. Exiting.")
            return
        # Run once if delay is 0, otherwise loop with delay
        if args.delay <= 0:
            await run_tests(servers)
        else:
            iteration = 1
            while True:
                print(f"\n{BOLD}Test Iteration #{iteration}{RESET}")
                all_success = await run_tests(servers)
                summary_border = f"\n{BOLD}{'=' * 80}{RESET}"
                print(summary_border)
                print(f"{BOLD}SUMMARY: {GREEN}All tests passed{RESET}" if all_success 
                      else f"{BOLD}SUMMARY: {RED}Some tests failed{RESET}")
                print(f"{BOLD}Waiting {args.delay} seconds before next test run...{RESET}")
                print(f"{BOLD}Press Ctrl+C to exit{RESET}")
                print(summary_border)
                
                # Wait with countdown
                wait_start = time.time()
                while time.time() - wait_start < args.delay:
                    # Sleep for a short time
                    # Sleep for a short time
                    await asyncio.sleep(1.0)
                    # Calculate and display remaining time
                    elapsed = time.time() - wait_start
                    remaining = args.delay - elapsed
                    
                    # Show countdown more frequently in a visually appealing way
                    if int(remaining) % 5 == 0 or remaining < 10:  # Show every 5 seconds or final countdown
                        percent_done = int((elapsed / args.delay) * 100)
                        # Build simple progress bar
                        progress = "=" * (percent_done // 5) + ">" + " " * (20 - (percent_done // 5))
                        print(f"\r{BOLD}{CYAN}[{progress}] {int(remaining)} seconds remaining... ({percent_done}%){RESET}", end="")
                        sys.stdout.flush()
                
                # Move to next line after countdown
                print()
    try:
        # Run once if delay is 0, otherwise loop with delay
        if args.delay <= 0:
            await run_tests(servers)
        else:
            iteration = 1
            while True:
                print(f"\n{BOLD}Test Iteration #{iteration}{RESET}")
                all_success = await run_tests(servers)
                summary_border = f"\n{BOLD}{'=' * 80}{RESET}"
                print(summary_border)
                print(f"{BOLD}SUMMARY: {GREEN}All tests passed{RESET}" if all_success 
                      else f"{BOLD}SUMMARY: {RED}Some tests failed{RESET}")
                print(f"{BOLD}Waiting {args.delay} seconds before next test run...{RESET}")
                print(f"{BOLD}Press Ctrl+C to exit{RESET}")
                print(summary_border)
                
                # Wait with countdown
                wait_start = time.time()
                while time.time() - wait_start < args.delay:
                    # Sleep for a short time
                    await asyncio.sleep(1.0)
                    # Calculate and display remaining time
                    elapsed = time.time() - wait_start
                    remaining = args.delay - elapsed
                    
                    # Show countdown more frequently in a visually appealing way
                    if int(remaining) % 5 == 0 or remaining < 10:  # Show every 5 seconds or final countdown
                        percent_done = int((elapsed / args.delay) * 100)
                        # Build simple progress bar
                        progress = "=" * (percent_done // 5) + ">" + " " * (20 - (percent_done // 5))
                        print(f"\r{BOLD}{CYAN}[{progress}] {int(remaining)} seconds remaining... ({percent_done}%){RESET}", end="")
                        sys.stdout.flush()
                
                # Move to next line after countdown
                print()
                iteration += 1
    except KeyboardInterrupt:
        print("\nTest loop interrupted by user. Exiting...")

def run_curses_app(stdscr):
    """Synchronous wrapper function for the async curses application"""
    # Run the async function in the current event loop
    try:
        # Create a new event loop for the curses app
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async main function
        return loop.run_until_complete(main_curses(stdscr))
    except Exception as e:
        # Ensure we restore the terminal properly
        curses.endwin()
        raise e

def main():
    """Main entry point that decides between curses and console mode"""
    # Parse arguments to check if curses should be used
    parser = argparse.ArgumentParser(description="Test OpenAI-compatible model server endpoints")
    parser.add_argument(
        "--delay", 
        type=int, 
        default=0, 
        help="Delay in seconds between test runs (0 for single run)"
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Run in console mode instead of curses UI"
    )
    parser.add_argument(
        "--cels-only",
        action="store_true",
        help="Test only non-OpenAI endpoints (e.g., CELS servers)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="model_servers.yaml",
        help="Path to model_servers.yaml file (default: model_servers.yaml)"
    )
    args = parser.parse_args()
    try:
        if args.console:
            # Run in console mode
            asyncio.run(main_async())
        else:
            # Run in curses mode using wrapper for proper initialization/cleanup
            curses.wrapper(run_curses_app)
    except KeyboardInterrupt:
        print(f"\n{BOLD}{YELLOW}Test loop interrupted by user. Exiting...{RESET}")
    except curses.error as e:
        print(f"\n{BOLD}{RED}Curses error: {e}{RESET}")
        print(f"{BOLD}Try running with --console flag if your terminal doesn't support curses{RESET}")
    except Exception as e:
        print(f"\n{BOLD}{RED}Error: {str(e)}{RESET}")

if __name__ == "__main__":
    main()

