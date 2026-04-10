# Provepy: Towards Autoformalizing python code using AI and Lean

This package provides a decorator `@provable` that tries to automatically formalize and prove your python functions.

Functions which fail to be proved will raise a `VerificationError`.
Functions which are proved to be correct will just run normally.

*Only works for simple functions without other decorators for now.*

**For best results, use a frontier model.**

This package is in alpha and contributions are welcome.

> [!CAUTION]
> This is experimental software and the proofs may not be perfect. Do not rely on this for critical applications.


## Installation


### Step 1: Install the package

To install from source (recommended for latest updates), clone the repository and run:

```bash
cd provepy
pip install -e .
```

To install from PyPI, run:

```bash
pip install provepy
```

### Step 2: Setup the lean environment

Navigate to your project folder ( from where you will run the python command) and run:

```bash
provepy init
```

Then add provepy_lean_project to your gitignore file if you have one as provepy_lean_project will contain a new git repository.

This will setup a lean environment in your project directory. It involves a large download so might take a while.

## Usage

Add the decorator @provable to every function you want to prove and pass the spec you want the function to follow  and the context (other functions used) to the decorator. Then just run the python command normally. Functions passed as context should be implemented in python, not C.

### Examples:

```python
from provepy import provable

@provable(claim="This function returns the sum of its inputs")
def add(a: int, b: int) -> int:
    return a+b
```

```python
from provepy import provable

def addTwo(a: int) ->int:
    return a+2

@provable(claim="This function returns the sum of its inputs plus two",context=[addTwo])
def add(a: int, b: int) -> int:
    return addTwo(a+b)
```


Type annotations are highly recommended. Currently, using only builtin types is also highly recommended.

## Configuration

The package supports using LLMs either via OpenRouter or through a OpenAI compatible api or directly through Google's Gemini API. You can toggle between these services using the `LLM_PROVIDER` environment variable. By default, the package uses the gemini api.

### Provider Selection
Set the environment variable `LLM_PROVIDER` to choose your backend:

* `gemini` (default)

* `custom` 

* `openrouter` 


---
### Google Gemini Configuration
To use Google's official API, ensure `LLM_PROVIDER` is unset or is set to `LLM_PROVIDER=gemini`. You can create a free API key from Google AI Studio. However generation on the free tier is very slow.

* **`GEMINI_API_KEY`**: Your Google API key (Required).
* **`GEMINI_MODEL_NAME`**: The exact model name used in the Google API (e.g., `gemini-3-flash-preview`). If not set, it defaults to the Gemma-31B model.
* **`BETTER_GEMINI_MODEL_NAME`**: (Optional) Specify a more powerful model (e.g., `gemini-3.1-pro-preview`) to use as a fallback when the primary model fails to prove a function.

---

### Custom  Configuration
To use a custom Open AI compatible api, ensure `LLM_PROVIDER` is explicitly set to `custom`.

* **`CUSTOM_API_KEY`**: Your custom API key (Required). 
* **`CUSTOM_API_URL`**: Your custom API URL (Required). 
* **`CUSTOM_MODEL_NAME`**: The specific model routing string to use.(Required)
* **`BETTER_CUSTOM_MODEL_NAME`**: (Optional) Specify a more powerful model to use as a fallback when the default, smaller model fails to prove a function.

---


### OpenRouter Configuration
To use OpenRouter, ensure `LLM_PROVIDER` is explicitly set to `openrouter`.

* **`OPENROUTER_API_KEY`**: Your OpenRouter API key (Required).
* **`OPENROUTER_MODEL_NAME`**: The specific model routing string to use. If not set, this defaults to `google/gemma-4-31b-it:free`.
* **`BETTER_OPENROUTER_MODEL_NAME`**: (Optional) Specify a more powerful model to use as a fallback when the default, smaller model fails to prove a function.

### Logging
To turn off Logs which are printed to stdout, set the environment variable `PROVEPY_LOG` to 0


## TODO:

1. Support other LLM Providers
2. Improve pulling context from outside the function
3. Allow other decorators on functions
4. Add support for repls
5. Add tests
6. Resolve name clashes between provided python functions and builtin mathlib objects
7. Store proofs for manual review
8. Improve prompts and use custom system prompts