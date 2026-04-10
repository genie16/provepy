import os
import re
import subprocess
import tempfile
import textwrap

from google import genai
from openai import OpenAI
from google.genai import types

from .utils import get_project_root

# Currently we only use the user mode to send these prompts even though they are named system_prompt.
# In the future we aim to use system prompts.
system_prompt_theorem="You are a lean 4 expert. Given here are a python function signature and a natural language specification. Write the lean 4 theorem signature for the natural language specification using the function signature. Follow the natural language specification strictly and if you use any imported objects from mathlib, verify that their semantics when used agree with the spec exactly. Follow every detail of the spec exactly and verify critically that you have not made any assumptions about the spec or mathlib that may be vague. The spec may not follow generally accepted conventions. In this case make sure you follow the spec exactly and not the convention. Write ONLY the lean 4 theorem signature. Do not write the function definition or the proof and do not output anything else and DO NOT include the `:=` symbol at the end. The only external library allowed is mathlib. Add any imports you need. Add only the minimal imports required."

system_prompt_code_translation="You are a lean 4 expert. Given here is a python code. Convert it to lean 4. The lean 4 code should match the python code exactly. Write the lean code in such a way that it is easy to prove properties about it while still making sure it matches the python code exactly. Keep the function signatures the same. Do not attempt to fix any bugs and do not make any assumptions. The only external library allowed is mathlib. Add any imports you need. Add only the minimal imports required. Do not output anything other than the lean code."

system_prompt_proof="You are a lean 4 expert. Given here are a definition and the theorem. Write the proof tactics to close it. Output only the tactics and nothing else. Output ONLY the sequence of tactics, do not include the := or by keywords. The only external library allowed is mathlib. Add any imports you need. Add only the minimal imports required. If the theorem is not provable, output only the word 'No' and nothing else."


_client = None
provider = os.getenv("LLM_PROVIDER", "gemini").lower()

log=bool(int(os.getenv("PROVEPY_LOG","1")))

def get_client():
    """Lazily initialize the client only ONCE and reuse it based on provider."""
    global _client
    
    if _client is not None:
        return _client
        
    if provider == "openrouter":
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    elif provider=="custom":
        _client = OpenAI(
            base_url=os.getenv("CUSTOM_API_URL"),
            api_key=os.getenv("CUSTOM_API_KEY")
        )       
    else:
        _client = genai.Client()
        
    return _client

# Set models dynamically based on the chosen provider
if provider == "openrouter":
    model_name = os.getenv('OPENROUTER_MODEL_NAME', "google/gemma-4-31b-it:free")
    better_model_name = os.getenv('BETTER_OPENROUTER_MODEL_NAME', None)
elif provider=="custom":
    model_name = os.getenv('CUSTOM_MODEL_NAME',None)
    better_model_name = os.getenv('BETTER_CUSTOM_MODEL_NAME', None)

else:
    model_name = os.getenv('GEMINI_MODEL_NAME', "gemma-4-31b-it")
    better_model_name = os.getenv('BETTER_GEMINI_MODEL_NAME', None)


def clean_llm_code(text: str) -> str:
    """Strips markdown code blocks from LLM output."""
    cleaned = re.sub(r'^```[a-zA-Z]*\n', '', text.strip())
    cleaned = re.sub(r'\n```$', '', cleaned)
    return cleaned.strip()

def extract_imports(*texts):
    """Extracts all import statements from texts and removes them from the original strings."""
    imports = []
    cleaned_texts = []
    
    for text in texts:
        # Find all import statements
        found = re.findall(r'^\s*import\s+.*$', text, flags=re.MULTILINE)
        for imp in found:
            imp = imp.strip()
            if imp not in imports:
                imports.append(imp)
        
        # Remove the imports from the text
        cleaned = re.sub(r'^\s*import\s+.*$\n?', '', text, flags=re.MULTILINE)
        cleaned_texts.append(cleaned.strip())
        
    return imports, cleaned_texts

def generate_theorem(signature, claim, system_prompt, model_name):
    client = get_client()
    prompt = (system_prompt + "\n"
            + "Function Signature: " + signature + "\n"
            + "Claim: " + claim)
            
    if provider == "openrouter" or provider=="custom":
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
    else:
        response = client.models.generate_content(
            model=model_name, contents=prompt,
            config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="high")
            ),
        )
        text = response.text
        
    if log: 
        print("\nTheorem:\n"+clean_llm_code(text)+"\n")
    return clean_llm_code(text)

def generate_code(code, system_prompt, model_name):
    client = get_client()
    prompt = (system_prompt + "\n"
            + "Function code: " + code)
            
    if provider == "openrouter" or provider=="custom":
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
    else:
        response = client.models.generate_content(
            model=model_name, contents=prompt,
            config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="high")
            ),

        )
        text = response.text
    if log: 
        print("Lean Code:\n"+clean_llm_code(text)+"\n")
    return clean_llm_code(text)


def try_verify(proof, definition, theorem, lake_path):
    # Extract imports to place them at the top of the file
    imports, (clean_proof, clean_definition, clean_theorem) = extract_imports(proof, definition, theorem)
    
    indented_tactics = textwrap.indent(clean_proof.strip(), '  ')
    imports_str = "\n".join(imports)
    
    lean_file_content = f"""{imports_str}

{clean_definition}
{clean_theorem} := by
{indented_tactics}
    """.strip()
    if log:
        print("Full lean file:\n"+lean_file_content+"\n")
    project_root = get_project_root()
    with tempfile.NamedTemporaryFile(
                dir=str(project_root),
                suffix='.lean', 
                delete=False, 
                mode='w', 
                encoding='utf-8'
            ) as temp_file:
        temp_file.write(lean_file_content)
        temp_file_path = temp_file.name

    try:
        result = subprocess.run(
            [lake_path, 'env', 'lean', temp_file_path],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=180
        )
        
        used_cheat = "sorry" in proof or "admit" in proof
            
        is_success = (result.returncode == 0) and not used_cheat
        return {
            "success": is_success,
            "output": result.stdout.strip(),
            "errors": result.stderr.strip(),
            "combined_code": lean_file_content
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "errors": "Lean compilation timed out (possible infinite tactic loop).",
            "combined_code": lean_file_content
        }
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def generate_and_verify_proof(definition, theorem, system_prompt, model_name, lake_path):
    client = get_client()

    init_prompt = (system_prompt + "\n"
            + "Function definition: " + definition + "\n"
            + "Theorem: " + theorem)
            
    if provider == "openrouter" or provider=="custom":
        messages = [{"role": "user", "content": init_prompt}]
        response = client.chat.completions.create(model=model_name, messages=messages)
        text = response.choices[0].message.content
        messages.append({"role": "assistant", "content": text})
    else:
        chat = client.chats.create(model=model_name,config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="high")
            ),
)
        response = chat.send_message(init_prompt)
        text = response.text
        

    proof = clean_llm_code(text)
    if log:
        print("Proof:\n"+proof+"\n")

    if proof.lower().replace(".", "").strip() == "no":
        return False, "LLM said function is not provable"

    results = try_verify(proof, definition, theorem, lake_path)
    verified = results["success"]
    error = results["output"] + "\n" + results["errors"]
    if log and not verified:
        print("Error:\n"+error+"\n")
    
    tries = 0
    max_tries = 3
    while (tries < max_tries and not verified):
        new_prompt = (f"I got this error when running using lean. Fix it. Output ONLY the full corrected sequence of tactics together, do not include the := or by keywords and do not include anything else.\n" +
        "The exact file compiled is: " + results["combined_code"] + "\n" +
        "The Error is: " + error)

        if provider == "openrouter" or provider=="custom":
            messages.append({"role": "user", "content": new_prompt})
            response = client.chat.completions.create(model=model_name, messages=messages)
            text = response.choices[0].message.content
            messages.append({"role": "assistant", "content": text})
        else:
            response = chat.send_message(new_prompt)
            text = response.text


        proof = text
        proof = clean_llm_code(text)
        if log:
            print("Retried Proof:\n"+proof+"\n")
        results = try_verify(proof, definition, theorem, lake_path)
        verified = results["success"]
        error = results["output"] + "\n" + results["errors"]
        if log and not verified:
            print("Error:\n"+error+"\n")

        tries += 1
        
    if verified:
        return True, None
    else:
        return False, error


def verify(code, signature, claim, lake_path):
    theorem = generate_theorem(signature, claim, system_prompt_theorem, model_name)
    function_definition = generate_code(code, system_prompt_code_translation, model_name)
    verified, error = generate_and_verify_proof(function_definition, theorem, system_prompt_proof, model_name, lake_path)
    
    if not verified and better_model_name:
        if log:
            print("\nTrying Better Model:\n")
        theorem = generate_theorem(signature, claim, system_prompt_theorem, better_model_name)
        function_definition = generate_code(code, system_prompt_code_translation, better_model_name)
        verified, error = generate_and_verify_proof(function_definition, theorem, system_prompt_proof, better_model_name, lake_path)

    return verified, error