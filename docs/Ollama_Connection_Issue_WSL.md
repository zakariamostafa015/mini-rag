# Ollama Connection Issue from WSL

## Problem

The RAG application was running inside **WSL (Ubuntu + Miniconda)**, while **Ollama** was running on the **Windows host**.

The application was configured with:

```env
OPENAI_API_URL=http://10.xxx.xxx.xxx:11434/v1/
```

When sending requests, the application returned:

```text
openai.APIConnectionError: Connection error.
httpcore.ConnectError: [Errno 111] Connection refused
```

Although Ollama was running successfully, the WSL environment could not reach the configured endpoint.

---

## Root Cause

The IP address (`10.xxx.xxx.xxx`) was not the correct Windows host address accessible from WSL.

Additionally, Ollama was initially listening only on:

```text
127.0.0.1:11434
```

which is not accessible from WSL.

---

## Resolution

### 1. Configure Ollama to listen on all interfaces

Start Ollama with:

```powershell
$env:OLLAMA_HOST="0.0.0.0:11434"
ollama serve
```

Verify that Ollama is listening on:

```text
Listening on [::]:11434
```

---

### 2. Find the Windows host IP

From Windows:

```powershell
ipconfig
```

Locate the **vEthernet (WSL)** adapter.

Example:

```text
IPv4 Address : 172.xx.xxx.x
```

---

### 3. Verify connectivity from WSL

```bash
curl http://172.xx.xxx.x:11434/v1/models
```

Expected response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen2.5:3b-instruct-q3_K_S"
    }
  ]
}
```

---

### 4. Update the application configuration

```env
GENERATION_BACKEND=OPENAI
GENERATION_MODEL_ID=qwen2.5:3b-instruct-q3_K_S
OPENAI_API_URL=http://172.xx.xxx.x:11434/v1/
```

Restart the application after updating the configuration.

---

## Result

The RAG application successfully connected to the local Ollama server through the OpenAI-compatible API, and inference requests completed successfully.