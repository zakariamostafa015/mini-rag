# mini-rag

This is minimal implementation of the RAG model for question asnwering

## Requirments

- Pythin 3.8 or later

### Install Python using MiniConda

1) Download and install MiniConda from [here(https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh)]
2) Create a new enviroment using the following command:
```bash
$ conda create -n mini-rag pythin=3.8
```
3) Activate the enviroment
```bash
$ conda activate mini-rag
```

## Installation

### Install the require packages

```bash
$ pip install -r requirements.txt
```

### Setup the enviroments variables

```bash
$ copy .env.example .env
```

Set your enviroment variables in the `.env` file. like `OPENAI_API_KEY` value.

### Setup the FastAPI server

```bash
$ uvicorn main:app --reload --host 0.0.0.0 --port 9500
```
