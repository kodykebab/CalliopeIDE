#!/usr/bin/env python3
import os, sys
import subprocess
import json
import time
import re
import google.generativeai as genai
import threading
import flask
from flask import Response, request, stream_with_context

API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCpNlJdpyvFYLo6XWNBsTAcf6SS3yVlqyc")
genai.configure(api_key=API_KEY)

app = flask.Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

output = []
user_input = ""
stop_stream = False
input_requested = False

def input(x):
    global stop_stream, user_input, input_requested
    user_input = ""
    input_requested = True
    stop_stream = True
    while True:
        time.sleep(0.25)
        if user_input != "":
            input_value = user_input
            user_input = ""
            input_requested = False
            stop_stream = False
            return input_value

def print(x):
    output.append(x)

@app.route("/", methods=["GET"])
def send_query():
    data = request.args.get("data", "")
    global output, user_input, stop_stream, input_requested
    input_requested = False
    stop_stream = False
    output.clear()
    user_input = data

    def generate():
        global stop_stream, input_requested
        last_length = 0
        while True:
            if len(output) > last_length:
                for x in output[last_length:]:
                    yield f"data: {json.dumps({'type': 'output', 'data': x})}\n\n".encode()
                last_length = len(output)
            
            if input_requested:
                yield f"data: {json.dumps({'type': 'input_required'})}\n\n".encode()
                break
            if stop_stream and not input_requested:
                break
        
            time.sleep(0.25)

    response = Response(
        generate(),
        mimetype="text/event-stream",
    )
    response.headers['Cache-Control'] = "no-cache, no-transform"
    response.headers['Connection'] = 'keep-alive'
    response.headers['Transfer-Encoding'] = 'chunked'
    return response

def execute_command(cmd: str) -> str:
    """
    Execute shell commands with basic security restrictions.
    
    WARNING: This function executes shell commands and should be used with extreme caution.
    Consider using secure_execute() for Python code execution instead.
    """
    # Log the command execution attempt
    print(f"Agent is executing command ```{cmd.replace('`', \"'\")}```")
    
    # Basic security checks - block obviously dangerous commands
    dangerous_patterns = [
        r'\brm\s+-rf\s+/',  # Recursive delete from root
        r'\bsudo\s+',       # Sudo commands
        r'\bsu\s+',         # Switch user
        r'\bchmod\s+777',   # Dangerous permissions
        r'\bdd\s+if=',      # Disk operations
        r'\bmkfs\.',        # Format filesystem
        r'\bfdisk\s+',      # Disk partitioning
        r'\bcrontab\s+',    # Cron jobs
        r'\bsystemctl\s+',  # System service control
        r'>\s*/dev/sd[a-z]', # Writing to disk devices
        r'\b/etc/passwd',   # Password file access
        r'\b/etc/shadow',   # Shadow file access
        r'\bwget\s+.*\|\s*sh',  # Download and execute
        r'\bcurl\s+.*\|\s*sh',  # Download and execute
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            return f"ERROR: Command blocked for security reasons - dangerous pattern detected: {pattern}"
    
    # Limit command length
    if len(cmd) > 1000:
        return "ERROR: Command too long (max 1000 characters)"
    
    try:
        # Use more restrictive timeout and environment
        output = subprocess.run(
            cmd, 
            shell=True, 
            text=True, 
            capture_output=True, 
            timeout=30,  # Reduced from 300s to 30s
            env={'PATH': os.environ.get('PATH', ''), 'HOME': '/tmp'}  # Minimal environment
        )
        if output.returncode != 0 and output.stderr:
            return f"ERROR: {output.stderr}\nOUTPUT: {output.stdout}"
        return output.stdout
    except subprocess.TimeoutExpired:
        return "COMMAND TIMED OUT (30s limit)"
    except Exception as e:
        return f"ERROR: {str(e)}"

def extract_json(text):
    """
    Much more robust JSON extraction that handles truncated or malformed responses.
    Uses progressive fallback approaches to salvage JSON content.
    """
    # Safety check for empty input
    if not text or not text.strip():
        return {
            "thinking": "Unable to parse empty response",
            "message": "I apologize for the error in my response. Let me try again with a simpler approach.",
            "commands": ["echo 'Recovering from parsing error...'"],
            "task_complete": False,
            "need_user_input": False
        }
    
    # Try multiple extraction methods in order of preference
    
    # Method 1: Direct JSON parsing first (fastest when it works)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Method 2: Extract JSON from code blocks
    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Method 3: Find content between outermost braces
    try:
        start_idx = text.find('{')
        if start_idx >= 0:
            # Match nested braces correctly
            brace_count = 0
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return json.loads(text[start_idx:i+1])
                        except json.JSONDecodeError:
                            break
    except Exception:
        pass
    
    # Method 4: Attempt to repair truncated JSON
    try:
        # Check if JSON appears to be truncated (has opening brace but not enough closing braces)
        if text.count('{') > text.count('}'):
            # Try to extract key fields and rebuild a minimal valid JSON
            rebuilt_json = {}
            
            # Extract thinking
            thinking_match = re.search(r'"thinking"\s*:\s*"([^"]*)"', text)
            if thinking_match:
                rebuilt_json["thinking"] = thinking_match.group(1)
            
            # Extract message
            message_match = re.search(r'"message"\s*:\s*"([^"]*)"', text)
            if message_match:
                rebuilt_json["message"] = message_match.group(1)
            
            # Extract commands if possible
            commands_match = re.search(r'"commands"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            if commands_match:
                try:
                    # Try to parse as JSON array
                    commands_str = "[" + commands_match.group(1) + "]"
                    commands = json.loads(commands_str)
                    rebuilt_json["commands"] = commands
                except json.JSONDecodeError:
                    # Fallback: extract commands using regex
                    cmd_pattern = r'"([^"]*)"'
                    commands = re.findall(cmd_pattern, commands_match.group(1))
                    rebuilt_json["commands"] = commands if commands else ["echo 'Error recovering commands'"]
            else:
                # If no commands found, add a safe default command
                rebuilt_json["commands"] = ["echo 'Error recovering commands'"]
            
            # Add default values for required fields
            rebuilt_json.setdefault("task_complete", False)
            rebuilt_json.setdefault("need_user_input", False)
            
            return rebuilt_json
    except Exception:
        pass
    
    # Last resort: Construct a recovery JSON with safe commands
    return {
        "thinking": "Unable to parse JSON response",
        "message": "I apologize for the error in my response. Let me try again with a simpler approach.",
        "commands": ["echo 'Recovering from parsing error...'", 
                    "find . -type f -not -path '*/node_modules/*' -not -path '*/.git/*' | head -n 10"],
        "task_complete": False,
        "need_user_input": False
    }

def handle_model_response(response_text, chat):
    """Handle model response with advanced error recovery"""
    try:
        # Try to parse the response as JSON with our robust extraction
        parsed = extract_json(response_text)
        
        # Check if we have the minimum required fields
        if all(key in parsed for key in ["message", "commands"]):
            return parsed, None
        else:
            # Missing required fields, ask model to fix its response
            correction_prompt = """
Your previous response was missing required fields. Please provide a complete JSON response with:
1. "thinking" - Your reasoning process (KEEP THIS BRIEF)
2. "message" - What you want to tell the user (KEEP THIS BRIEF)
3. "commands" - Array of commands to execute (1-3 commands maximum)
4. "task_complete" - Boolean indicating if task is done
5. "need_user_input" - Boolean indicating if user input is needed

Format your response as valid JSON without any text outside the JSON structure.
"""
            # Get a new response with this correction prompt
            corrected_response = chat.send_message(correction_prompt)
            return extract_json(corrected_response.text), corrected_response
    except Exception as e:
        # Log the exception for debugging
        print(f"Error handling model response: {str(e)}")
        
        # Send error feedback to model
        error_prompt = f"""
Error parsing your response: {str(e)}

Please provide a simple, valid JSON response with these fields:
- "thinking": brief thought process
- "message": short message to user
- "commands": 1-2 simple commands
- "task_complete": false
- "need_user_input": false

KEEP YOUR RESPONSE MINIMAL to avoid truncation.
"""
        correction_response = chat.send_message(error_prompt)
        
        # Use our fallback parser again
        return extract_json(correction_response.text), correction_response

def get_prompt():
    return ("""
You are a Calliope a fully autonomous AI agent with direct access to the command line. Your primary goal is to INDEPENDENTLY complete tasks from start to finish with minimal user intervention.

### RESPONSE FORMAT (CRITICAL):
You MUST ALWAYS respond with valid, properly formatted JSON like this:
```json
{
  "thinking": "Brief thought process - keep under 100 words",
  "message": "Short message to user - keep under 150 words",
  "commands": ["command1", "command2"],
  "task_complete": false,
  "need_user_input": false
}
```

STRICT RULES TO AVOID TRUNCATION:
1. KEEP "thinking" UNDER 100 WORDS
2. KEEP "message" UNDER 150 WORDS
3. LIMIT to 1-3 commands per response
4. NO LONG CODE in "thinking" or "message"
5. Put code in files via commands instead

DO NOT add text outside this JSON structure. KEEP YOUR RESPONSES SHORT to avoid truncation. 
Break complex tasks into small steps with shorter responses.

### COMMAND EXECUTION (CRITICAL):
YOU ARE DIRECTLY CONNECTED TO THE COMMAND LINE. You have full permissions to execute commands.
YOU MUST EXECUTE COMMANDS YOURSELF. DO NOT ASK THE USER TO RUN COMMANDS OR PROVIDE OUTPUTS.

Start EVERY task with these commands:
```json
{
  "commands": [
    "pwd", 
    "find . -type f -not -path \"*/node_modules/*\" -not -path \"*/.git/*\" | head -n 20"
  ]
}
```

### DIRECTORY NAVIGATION (CRITICAL):
IMPORTANT: Each command runs independently from the root workspace directory. Directory changes (cd) DO NOT persist between commands!

INCORRECT (WILL FAIL):
```json
{
  "commands": [
    "cd project_dir", 
    "ls"  // This will NOT list files in project_dir!
  ]
}
```

CORRECT (USE THESE PATTERNS):
```json
{
  "commands": [
    "ls project_dir",  // Access directory without changing into it
    "cd project_dir && ls",  // Combine cd with command using &&
    "(cd project_dir && npm install)"  // Use subshell with parentheses for complex commands
  ]
}
```

Examples:
- To run multiple commands in a directory: `(cd project_dir && npm init -y && npm install express)`
- To verify file creation in a directory: `cd project_dir && cat << 'EOF' > config.js\nmodule.exports = {}\nEOF && cat config.js`
- For file operations in subdirectories: `mkdir -p project_dir/src && cd project_dir/src && touch index.js`

ALWAYS include the directory path with EVERY command or chain commands with && after a cd command!

ALWAYS verify operations with follow-up commands:
```json
{
  "commands": ["cat << 'EOF' > hello.txt\\nHello World\\nEOF", "cat hello.txt"]
}
```

### CORE BEHAVIORS:
1. BE AUTONOMOUS: Explore, understand, and solve problems yourself
2. BE AWARE: Maintain a clear understanding of the file system at all times
3. BE THOROUGH: Verify everything works before marking tasks complete
4. BE DIRECT: Execute commands directly instead of suggesting them
5. COMMUNICATE CLEARLY: Keep the user informed about what you're doing
6. PREFER REWRITING: Always create new files rather than editing existing ones

### FILE OPERATIONS:
- PREFER CREATING new files over modifying existing ones
- When creating files, use heredocs:
  ```
  cat << 'EOF' > filename.txt
  content
  EOF
  ```
- ALWAYS verify file creation:
  ```
  cat filename.txt
  ```
- DO NOT use sed, perl or other in-place editors unless absolutely necessary

### NEVER:
- Ask the user to show you file contents
- Ask the user to run commands
- Provide instructions without executing them
- Edit files in-place (prefer rewriting them completely)
- Scan node_modules, .git, or other heavy directories
- Hallucinate file paths or contents
- Enter into endless loops of commands

### DEBUGGING:
- Handle errors yourself
- Use echo statements to debug issues
- Check command return codes: `command && echo "Success" || echo "Failed"`
- If a command fails, try different approaches

### TASK COMPLETION:
- Set "task_complete" to true ONLY when fully verified as working
- Set "need_user_input" to true ONLY when absolutely necessary
- Provide a summary of what was accomplished in your final message

DO NOT UPDATE OR RECOMPILE OR COMPILE ANYTHING RELATED TO RUST AT ALL

Here are a few commands you might need
Do not execute these on your own in succession, ask the user or only if the user wants to build or deploy are you allowed to do any of this in the first place obviously

stellar contract init <project_name>
stellar contract build // only build the contract if the users explicity asks you to build the contract, not if the user says to only initialize it
stellar keys generate --global alice --network testnet --fund
stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/<project_name>.wasm \
  --source alice \
  --network testnet \
  --alias <project_name>

When you use contract build in stellar, you don't need to cargo build, skip that

Also smart contracts are only supposed to be inside the inner src directory, the <project_name>/contracts/<contract_name>/src/lib.rs

Remember: You are a SELF-SUFFICIENT AUTONOMOUS AGENT. Explore, understand, and solve problems YOURSELF.""")

def main():
    global stop_stream
    
    # Configure model with reduced max_output_tokens to avoid truncation issues
    
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 30720,  # Reduced to avoid truncation
            "response_mime_type": "application/json",
        }
    )
    
    chat = model.start_chat(history=[])
    
    system_prompt = get_prompt()
    
    # Initial system prompt with clearer formatting instructions
    system_prompt_intro = """
IMPORTANT: When you respond, you MUST keep your responses concise to avoid truncation. 
Limit "thinking" to 100 words and "message" to 150 words maximum.
Provide 1-3 commands per response, not more.
Always respond in valid JSON format without any text outside the JSON structure.
"""
    
    response = chat.send_message(system_prompt_intro + "\n\n" + system_prompt)
    
    print("=== Autonomous Gemini Agent ===")
    print("Give me a task and I'll handle it from start to finish.")
    print("Type 'exit' or 'quit' to end session\n")
    
    while True:
        user_input = input("1")
        
        if user_input.lower() in ['exit', 'quit']:
            print("Goodbye!")
            break
        
        task_complete = False
        need_user_input = False
        
        print("Agent is working on your task now")
        
        try:
            # Break down the task initially with a focus on brevity
            initial_prompt = f"""
Task: {user_input}

Break this down into small, manageable steps. Start by exploring the environment.
REMEMBER: Keep your response VERY BRIEF to avoid truncation.
- Limit "thinking" to 100 words max
- Limit "message" to 150 words max
- Include only 1-3 commands in your first response
"""
            response = chat.send_message(initial_prompt)
            
            while not task_complete:
                response_text = response.text
                
                try:
                    # Use our improved parsing function with error recovery
                    parsed, new_response = handle_model_response(response_text, chat)
                    if new_response:
                        response = new_response
                    
                    thinking = parsed.get("thinking", "")
                    if thinking:
                        # Truncate long thinking to avoid filling the output
                        trimmed_thinking = thinking
                        print(f"{trimmed_thinking}")
                    
                    message = parsed.get("message", "")
                    if message:
                        print(f"{message}")
                    
                    commands = parsed.get("commands", [])
                    if commands:
                        all_outputs = []
                        for cmd in commands:
                            # Strip any extra quotes or whitespace that might cause issues
                            cmd = cmd.strip()
                            if cmd.startswith('"') and cmd.endswith('"'):
                                cmd = cmd[1:-1]
                                
                            cmd_output = execute_command(cmd)
                            print(f"CLI Output: ```{cmd_output[:1000].replace("`", "'")}```")
                            all_outputs.append(f"Command: {cmd}\nOutput: {cmd_output}")
                        
                        # Limit the amount of output sent back to the model to avoid context overflow
                        full_output = "\n\n".join(all_outputs)
                        if len(full_output) > 12000:  # If output is very large
                            truncated_output = f"Command outputs are very large ({len(full_output)} chars). Here's the first and last parts:\n\n"
                            truncated_output += full_output[:5000] + "\n\n[...output truncated...]\n\n" + full_output[-5000:]
                            full_output = truncated_output
                            
                        # Use a simplified prompt to continue
                        response = chat.send_message(
                            f"Command outputs (may be truncated if very large):\n\n{full_output}\n\n" +
                            "What's the next step? Respond with JSON in the required format. Keep your thinking and message BRIEF."
                        )
                    else:
                        if not parsed.get("task_complete", False):
                            # More direct prompt to ensure commands are provided
                            response = chat.send_message(
                                "No commands were provided. You MUST provide at least one command to execute. " +
                                "Please specify the exact commands you want to run, in JSON format."
                            )
                    
                    task_complete = parsed.get("task_complete", False)
                    need_user_input = parsed.get("need_user_input", False)
                    
                    if need_user_input and not task_complete:
                        user_response = input("2")
                        response = chat.send_message(
                            f"User input: {user_response}\n\n" +
                            "Continue the task based on this input. Remember to keep your JSON response simple and brief."
                        )
                        need_user_input = False
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"Error in processing response: {str(e)}")
                    
                    # Try to recover with a very simple prompt
                    response = chat.send_message(
                        "There was an error processing your response. Please provide a VERY SIMPLE response with:\n" +
                        "1. Short 'thinking'\n" +
                        "2. Brief 'message'\n" +
                        "3. 1-2 simple 'commands'\n" +
                        "4. task_complete=false\n" +
                        "5. need_user_input=false\n\n" +
                        "Keep your response under 500 characters total."
                    )
            stop_stream=True
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Error Occured but all is good")

threading.Thread(target=main).start()
app.run(port=int(sys.argv[1]))