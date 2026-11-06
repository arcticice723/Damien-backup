# Damien

Damien is a free, local Windows desktop assistant built with Python 3.13 and Ollama. It uses no paid APIs and no paid cloud services.

## Current Stage

Stage 1 is implemented: polished desktop window, text chat, streaming Ollama responses, push-to-talk speech recognition, local text-to-speech, conversation history, approved app commands, inspectable optional memory, approved-document retrieval, model selection for the current session, and a benchmark tab/script.

Stage 2 is implemented: Windows system tray, minimize/close to tray, restore from tray, quit from tray, microphone mute/unmute from tray, visible listening and Ollama connection status, optional launch at Windows sign-in, and configurable local wake phrase detection for `Hey Damien`.

Stage 3 is implemented as a reliable Windows `.exe` folder build plus an optional desktop shortcut script. It does not require admin mode, CUDA, Developer Mode, paid APIs, cloud services, OpenAI keys, or `HF_TOKEN`.

Stage 4 foundation is implemented: Damien now has a Jarvis-class orchestration spine with free/local-first routing, low-risk tool execution policy, JSONL audit logging, richer categorized memory records, broader approved-file retrieval, controlled web lookup hooks, voice interruption hooks, cinematic voice status copy, and a Windows single-instance guard that focuses the existing app instead of launching duplicate Damien processes.

## Hardware Inspection

Inspected on this machine:

- GPU: NVIDIA GeForce RTX 4060
- VRAM: 8,188 MB total, about 1,370 MB free at inspection time
- Driver: 595.95
- System RAM: 34,064,289,792 bytes, about 31.7 GiB
- Python selected: 3.13.14
- Ollama installed: 0.32.1

`qwen3.5:9b` is available in Ollama and is marked as supporting tools and thinking. Ollama lists `qwen3.5:latest` at 6.6 GB with a 256K context window, and the 9B tag is part of that family. On an 8 GB RTX 4060, that is borderline rather than comfortable once KV cache and desktop GPU usage are included. Damien currently defaults to your already-installed `llama3:latest` so stage 1 runs now. The first upgrade to benchmark is:

```powershell
ollama pull qwen3.5:9b
```

After pulling it, change one setting in `config/settings.json`:

```json
"model": "qwen3.5:9b"
```

Sources: [Ollama qwen3.5:9b](https://ollama.com/library/qwen3.5%3A9b), [Ollama qwen3.5 tags](https://ollama.com/library/qwen3.5/tags), and [Ollama tool calling docs](https://docs.ollama.com/capabilities/tool-calling).

## Setup

This installs packages into `.venv` inside this folder only:

```powershell
.\scripts\setup.ps1
```

Run Damien:

```powershell
.\scripts\run.ps1
```

For speech diagnostics:

```powershell
.\scripts\check_speech.ps1
```

The setup script creates `.venv` with Python 3.13 if it is missing and installs base plus speech dependencies there. It does not install packages into global Python, require admin mode, require CUDA, require Windows Developer Mode, or require `HF_TOKEN`.

## How to install/run Damien

For development/source runs:

```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
```

To build the Windows app:

```powershell
.\scripts\build.ps1
```

The packaged app is created here:

```powershell
dist\Damien\Damien.exe
```

Run it directly:

```powershell
.\dist\Damien\Damien.exe
```

Create a desktop shortcut:

```powershell
.\scripts\create_shortcut.ps1
```

The packaged app keeps editable files beside the executable:

```text
dist\Damien\config\settings.json
dist\Damien\config\approved_apps.json
dist\Damien\logs\damien.log
dist\Damien\history\
dist\Damien\memory\
dist\Damien\approved_documents\
```

Edit `dist\Damien\config\settings.json` after packaging if you want packaged Damien to use different settings than the source tree.

## Normal Usage

Launch Damien:

```powershell
.\scripts\run.ps1
```

Use the Conversation tab to type messages or hold `Hold to Talk` for push-to-talk voice input. Damien streams local Ollama responses into the chat window and speaks responses with local text-to-speech.

To debug voice end to end, open Settings and click `Voice Diagnostics`. It checks Python/venv, microphone devices, microphone recording, Whisper loading, speech transcription, Ollama connection, model response, TTS, and wake phrase status. Failures are shown in the conversation window with a specific fix where Damien can infer one.

Closing or minimizing the window keeps Damien running in the Windows system tray when tray dependencies are installed. From the tray menu you can:

- Restore the window.
- Mute or unmute the microphone.
- See microphone, wake phrase, and Ollama connection status.
- Quit Damien completely.

The Settings tab includes:

- Ollama model selection.
- Thinking mode selection.
- Microphone device selection.
- Voice output device selection for Windows speech output.
- Background tray startup, so wake phrase and voice responses work without showing the window.
- Wake phrase enable/disable.
- Launch at Windows sign-in.

## Convenience Abilities

Damien can now run low-risk convenience actions automatically while keeping dangerous actions blocked:

- Open approved apps such as Calculator, Notepad, Paint, File Explorer, Task Manager, Control Panel, and Snipping Tool.
- Ask what apps are approved with `list approved apps`.
- Open websites or browser searches, for example `open example.com`.
- Copy user-provided text to the clipboard, for example `copy call me later to clipboard`.
- Save local notes with `take a note ...` and read them with `show my notes`.
- Open approved Damien folders: `open notes folder`, `open logs folder`, `open settings folder`, or `open approved documents folder`.
- Read local time/date and local system status.

High-risk requests such as deletion, purchases, credential handling, installs, downloads, shutdowns, and destructive system changes remain denied or confirmation-gated.

## Use Damien From Other Devices

Damien includes a password-protected remote portal for phones, tablets, and laptops.

For home Wi-Fi, open the LAN address shown in Settings → Automation. For secure away-from-home access, install Tailscale on both the Damien PC and phone, sign both into the same tailnet, then configure Tailscale Serve once from an Administrator PowerShell window:

```powershell
& "$env:ProgramFiles\Tailscale\tailscale.exe" serve --bg 8765
```

Tailscale Serve keeps the portal available privately to your tailnet and provides an HTTPS address. If prompted, approve enabling HTTPS for your tailnet. Damien shows the `Away (Tailscale HTTPS)` address in Settings → Automation after you sign in and restart Damien. Open it from your phone while Tailscale is connected, enter the portal password, and send a text command. The command runs through the same Damien assistant pipeline as typed or spoken commands on the PC.

Set a fixed password under Settings → Automation; passwords must be at least 12 characters. The password is never written to the log. On home Wi-Fi, the portal uses unencrypted HTTP; use only a trusted network. Do not expose this port directly to the public internet or use Tailscale Funnel for this private portal.

Install Tailscale from [the official Windows download](https://tailscale.com/download/windows) and the official [iOS](https://tailscale.com/download/ios) or [Android](https://tailscale.com/download/android) download page. After signing in on both devices, restart Damien if the Tailscale address is not listed. You can also check the PC address in PowerShell with `tailscale ip -4`.

Launch at sign-in is disabled by default. Enabling it asks for confirmation because it writes to the current user's Windows startup registry key.

## Wake Phrase

Wake phrase support is local/free and configurable in Settings. When enabled, Damien listens for:

```text
Hey Damien
```

Idle detection uses short local microphone windows and a smaller local Whisper model by default:

```json
"wake_whisper_model": "tiny",
"wake_whisper_device": "cpu",
"wake_whisper_compute_type": "int8"
```

Full push-to-talk speech recognition also defaults to CPU/int8:

```json
"whisper_device": "cpu",
"whisper_compute_type": "int8"
```

CUDA speech is optional. If you explicitly set speech to CUDA and Damien cannot load CUDA/cuBLAS DLLs, Damien falls back to CPU/int8 and keeps the app running.

After Damien hears the wake phrase, it records a short command window, runs the normal local speech-to-text path, and sends the command to Ollama. Push-to-talk remains available as the fallback.

If wake phrase dependencies are missing or fail to load, Damien keeps running and push-to-talk still works. Damien does not save raw microphone audio by default.

To improve recognition for names and uncommon words, open Settings → Voice. Add names and terms as a comma-separated list. Add corrections as `misheard=correct` pairs separated by semicolons, such as `damean=Damien; hermies=Hermes`. Damien includes those terms in Whisper's recognition context and applies the exact corrections after transcription. The full speech model unloads after five minutes without transcription and reloads when needed. Wake detection skips near-silent audio windows so it can release its small model during quiet periods.

## Privacy Controls

- Damien does not save raw microphone audio by default.
- Push-to-talk is always available.
- Wake phrase capture only runs when enabled and the microphone is not muted.
- The visible mic control immediately blocks microphone capture.
- Long-term memory is disabled by default.
- Long-term memory, when enabled, is stored in `memory/long_term_memory.jsonl` and can be inspected or deleted from the Memory tab.
- Retrieval reads only `.txt` and `.md` files under `approved_documents/`.

## Safe Tools

Damien cannot execute unrestricted commands. Tool handling is routed through a risk policy:

- Low-risk actions may run automatically, such as searching approved files, reading system status, opening approved apps, controlled web lookup, and inspectable memory reads.
- Important actions must require confirmation before implementation.
- Dangerous actions such as deletion, purchasing, credential handling, installation, and destructive system changes are denied by default.
- To run a PowerShell command, say `run PowerShell: <command>`. Damien shows the exact command and waits for `confirm` or `cancel`. Common dangerous operations remain blocked.
- Relevant approved documents can be added to local answers; Damien treats document text as reference material and names the source file.

Tool activity and provider routing are logged to:

```text
logs\audit.jsonl
```

Free-only mode is enabled by default:

```json
"free_only_mode": true
```

When free-only mode is on, Damien blocks paid cloud providers even if a cloud API key is configured. Cloud routing remains disabled by default and should stay off if you want Damien to remain completely free/local.

Free workarounds to prefer before any paid service:

- Use local Ollama models for chat and reasoning.
- Use approved local documents for retrieval.
- Use controlled web lookup for public information.
- Use local speech recognition/TTS defaults.
- Benchmark stronger free local models before considering cloud APIs.

## Benchmarking

From the app, use the Benchmark tab. From development PowerShell:

```powershell
.\scripts\benchmark_model.ps1 --model llama3:latest
```

The benchmark streams the response and prints timing plus GPU memory before/after.

## Troubleshooting

### Windows Defender or SmartScreen warns about Damien.exe

The local build is unsigned, so Windows may warn the first time you run it. Build output is local to this folder and uses PyInstaller with the project `.venv`. If Defender quarantines the executable, rebuild with:

```powershell
.\scripts\build.ps1
```

Then allow the app only if you trust this local source tree. Damien does not require admin mode.

### Packaged app says dependencies are missing

Build from the project virtual environment:

```powershell
.\scripts\setup.ps1
.\scripts\build.ps1
```

Run the packaged executable from `dist\Damien\Damien.exe`, not from inside PyInstaller's internal folders. The editable `config`, `logs`, `history`, `memory`, and `approved_documents` folders should sit beside `Damien.exe`.

### Damien says Ollama is not running

Damien checks the local Ollama server at startup. If Ollama is not reachable, the app stays open and shows a local connection panel with three recovery actions:

- `Start Ollama`: tries to run `ollama serve` automatically on this computer.
- `Retry`: checks the local Ollama connection again.
- `Open Settings`: opens Damien's model/settings tab so you can verify the configured model and server URL.

You can also start Ollama manually from Windows, then press `Retry` in Damien. The default local URL is:

```text
http://127.0.0.1:11434
```

If `ollama serve` reports this message:

```text
listen tcp 127.0.0.1:11434: bind: Only one usage of each socket address is normally permitted.
```

that usually means Ollama is already running on the configured local port. Damien treats that as a likely success and probes:

```text
http://127.0.0.1:11434/api/tags
```

Connection diagnostics are written locally to:

```text
logs/damien.log
```

No paid API, cloud service, or OpenAI key is used.

This works the same in the packaged app. `Start Ollama` still tries to run `ollama serve`, and `Retry` still probes the configured local server.

### Damien says Ollama is reachable but chat failed with Bad Request

Damien uses Ollama's `/api/chat` endpoint for chat messages. `/api/generate` is for prompt-style completion, so it is not the right default for Damien's conversation history.

For `llama3:latest`, Damien now sends a basic chat payload without tools:

```json
{
  "model": "llama3:latest",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true,
  "options": {
    "temperature": 0.25,
    "num_ctx": 4096
  }
}
```

Before enabling Ollama tool calling, Damien checks `/api/tags` and only sends the `tools` field when the selected model advertises tool support. Your installed `llama3:latest` reports `completion` capability only, so tools are disabled for that model.

When a chat request fails, Damien logs the non-secret endpoint, model name, HTTP status, and Ollama response body to:

```text
logs/damien.log
```

Voice logs also go to `logs/damien.log`, including selected microphone/device discovery, recording start/stop, transcription text, Ollama request start/finish, TTS start/finish, and wake phrase state changes.

### Speech Dependencies Are Missing

If Damien shows messages like:

```text
Install sounddevice before using microphone input.
Install faster-whisper before using speech recognition.
```

run:

```powershell
.\scripts\setup.ps1
.\scripts\check_speech.ps1
```

The diagnostics check:

- The Python executable being used.
- `sounddevice` import.
- Microphone devices.
- `faster-whisper` import.
- Local `tiny` model load on CPU/int8.
- `pyttsx3` import.
- Basic TTS initialization.

For the packaged app, rebuild after fixing dependencies:

```powershell
.\scripts\build.ps1
```

### Microphone Issues

Open Settings and use the microphone dropdown. Choose the real input device, then click `Test Microphone`. Damien shows the measured volume level. If it reports:

```text
This microphone is not picking up sound.
```

choose another microphone, check Windows microphone privacy permissions, and confirm the input device is not muted. The selected microphone is saved in:

```text
config\settings.json
```

For packaged Damien, the file is:

```text
dist\Damien\config\settings.json
```

Run speech diagnostics from source with:

```powershell
.\scripts\check_speech.ps1
```

### CUDA/cuBLAS Speech Errors

Damien does not require CUDA for speech. Defaults are CPU/int8 specifically for reliability:

```json
"whisper_device": "cpu",
"whisper_compute_type": "int8"
```

If you explicitly enable CUDA and see an error like:

```text
Library cublas64_12.dll is not found or cannot be loaded.
```

Damien falls back to CPU/int8 automatically. GPU acceleration for speech is optional and not required.

### Hugging Face Warnings

`faster-whisper` may download free local model files the first time a model is used. No account or `HF_TOKEN` is required for the default Whisper models. Damien sets:

```text
HF_HUB_DISABLE_SYMLINKS_WARNING=1
```

to suppress the non-fatal Windows symlink cache warning. Admin mode and Windows Developer Mode are not required.

If Windows shows speech model download warnings, let the free model download finish. These are local model files used by `faster-whisper`; they are not paid APIs and do not require credentials.

## Uninstall

Quit Damien from the tray menu first.

For the packaged app, remove:

```text
dist\Damien\
```

If you created a desktop shortcut, delete:

```text
Desktop\Damien.lnk
```

If you enabled launch at Windows sign-in, open Damien Settings and turn it off before deleting the app. If the app is already removed, delete the current-user startup registry value named `Damien` from:

```text
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
```

For source/development cleanup, you can also remove `.venv`, `logs`, `history`, and `memory` from this project folder if you no longer need them.

## Tests

```powershell
.\scripts\run_tests.ps1
```

Tests avoid microphone, TTS, and live Ollama hardware requirements.

## Project Structure

```text
approved_documents/
config/
  approved_apps.json
  settings.json
scripts/
  benchmark_model.py
  benchmark_model.ps1
  check_speech.py
  check_speech.ps1
  check_runtime.ps1
  build.ps1
  create_shortcut.ps1
  package_exe.ps1
  run.ps1
  run_tests.ps1
  setup.ps1
  setup_speech.ps1
  setup_venv.ps1
src/jarvis_assistant/
  ai/
  app.py
  audio.py
  commands.py
  config.py
  conversation.py
  memory.py
  retrieval.py
  speech.py
  system_metrics.py
tests/
main.py
```
