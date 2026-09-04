# Model world example (optional)

A GGUF model is folded into an `.fs` world file. Through MoliLine you can:

- `ON|A` boot world A (embedded llama.cpp engine — no Ollama),
- let a live model A enter world B (`ACT|ENTER|B`), write into B's files
  (`ACT|WRITE|B|file|text`), and return home (`ACT|HOME`),
- save runtime changes back into the world file (`ACT|SAVE|B`),
- run an agent that operates a program world with an allowlisted toolset
  (`agent_demo.py`).

## Requirements

- Windows (MoliLine binaries).
- A GGUF model file.
- Python with `llama-cpp-python`:

```bash
pip install -r requirements.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

## Usage

```bash
python run_demo.py --gguf <model.gguf> --out .\demo --engine-python <python-with-llama-cpp>
python agent_demo.py --gguf <model.gguf> --out .\agent_demo
```

## Notes

- Runtime writes land in the unfolded working world; `SAVE` folds them back
  into a new `.fs`.
- The demo copies one GGUF into two worlds; production can share one content
  pool instead.
- An inference library is still required (weights do not execute
  themselves). No Ollama, no manual loader steps.

