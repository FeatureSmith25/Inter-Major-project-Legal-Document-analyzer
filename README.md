# AI-Powered Legal Document Analyzer

A local-first document intelligence application for PDF/DOCX review. It extracts document text, detects common clause categories and dates, provides evidence-linked retrieval, flags text patterns for human review, and compares two versions. **This is an analysis and assistance tool, not legal advice.**

## Architecture

```text
Browser dashboard (HTML/CSS/JavaScript) → FastAPI → PDF/DOCX extraction (+ optional OCR)
                                  → metadata-preserving chunks → SQL database
                                  → sentence-transformer retrieval (TF-IDF fallback)
                                  → optional OpenAI-compatible LLM → cited answer
                                  → clause/date/attention analysis and comparison
```

The API, UI, document processing, retrieval, analysis, prompts, and persistence live in separate modules. Every chunk carries its document ID, page, section, clause, and text. DOCX does not have reliable fixed pagination, so DOCX citations use page 1 plus the available section/clause locator.

## Requirements and setup

- Python 3.10 or newer
- Tesseract OCR installed separately if scanned-PDF OCR is enabled
- An optional OpenAI-compatible chat completion endpoint for generated answers

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The standard install uses TF-IDF retrieval so setup stays small. To enable semantic Hugging Face embeddings (PyTorch is a larger download), also install `python -m pip install -r requirements-embeddings.txt`.

By default, the application uses SQLite in `data/legal_analyzer.db`. Set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL to use PostgreSQL. Uploaded content is processed in memory and is not copied to an uploads directory. The existing `legal_contract_clauses.csv` is retained as project data and is not ingested automatically.

## Run the application

Start the application in one terminal. FastAPI serves both the browser dashboard and API from the same origin:

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the dashboard. The API health check is `http://127.0.0.1:8000/health`; interactive API documentation is at `http://127.0.0.1:8000/docs`.

## Deploy on Vercel

The project is configured for Vercel's Python runtime. Import the GitHub repository in Vercel and deploy from the project root. The dashboard is served by FastAPI, and `vercel.json` includes the `frontend/` assets in the function bundle.

Before deploying, create a persistent PostgreSQL database and add its SQLAlchemy URL to the Vercel project's environment variables as `DATABASE_URL` (for example, `postgresql+psycopg://...`). Do not use the default SQLite URL in production: Vercel function filesystems are temporary, so SQLite data can disappear and may differ between function instances.

Add `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in Vercel if generated chat answers are needed. Configure `USER_TOKENS_JSON` to require bearer tokens; otherwise the app runs in single-user local mode. Never commit `.env` or paste secrets into source files. Scanned-document OCR requires a Tesseract executable and is not enabled by default.

After setting the environment variables, redeploy so the function starts with the production configuration. Verify the deployment at `/health`, then upload a test document and confirm it remains available after a new deployment.

## Configuration

Copy `.env.example` to `.env` and set values as needed:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection (SQLite by default; PostgreSQL supported) |
| `MAX_UPLOAD_MB` | Per-file size limit (default 25 MB) |
| `OCR_ENABLED` | Set `true` to OCR PDF pages with very little extracted text |
| `TESSERACT_CMD` | Optional full path to the Tesseract executable |
| `EMBEDDING_MODEL` | Sentence Transformers model when the optional embedding package is installed; first use may download weights |
| `LLM_BASE_URL` | OpenAI-compatible API base URL (for example, a provider's `/v1`) |
| `LLM_API_KEY` | Secret for the configured chat endpoint; never commit `.env` |
| `LLM_MODEL` | Chat model identifier |
| `USER_TOKENS_JSON` | Optional JSON map from bearer tokens to user IDs; documents and history are scoped to that user ID |

When no LLM is configured or the endpoint fails, Q&A labels its response as source excerpts rather than presenting it as a model answer. Follow-up turns send recent chat context to the model to resolve references, but each answer must still be based on newly retrieved document evidence. If configured, the LLM provider receives the question, recent chat context, and retrieved document passages; review that provider's data-handling terms before sending confidential documents. The first semantic search may download the configured embedding model. If it cannot load, retrieval falls back to TF-IDF. OCR requires the separate Tesseract executable as well as the Python dependencies.

## API endpoints

- `POST /api/documents` — upload and process one PDF/DOCX
- `GET /api/documents` — list document history
- `GET /api/documents/{id}` — return document analysis
- `POST /api/documents/{id}/ask` — ask a question against retrieved evidence
- `DELETE /api/documents/{id}` — remove a document and its chunks
- `POST /api/compare` — compare two uploaded files

## Current behavior and limitations

- Clause detection and attention prompts are transparent text-pattern checks. A missing match does not establish that a clause is absent.
- Comparison reports text similarities and differences; it does not determine legal effect or whether a change is favorable.
- If `USER_TOKENS_JSON` is blank, the app runs in tokenless local single-user mode. For multiple users, configure a JSON object mapping unique high-entropy tokens to stable user IDs, for example `{"secret-token-a":"user-a","secret-token-b":"user-b"}`. The browser dashboard accepts the bearer token, and document list/read/delete operations are owner-scoped. Use HTTPS and a proper secret manager when exposing the service beyond a trusted local environment.
- PostgreSQL is supported for metadata persistence. Embeddings are computed at retrieval time; there is no persisted vector index in this initial version.
- Logs do not include extracted document text. Avoid adding document content to application logs or error telemetry.

## Tests

```powershell
python -m pytest
```

Tests cover upload validation, DOCX extraction and chunk locators, unsupported questions, source evidence, and comparison output. A deployment should add OCR fixtures, API integration tests, access-control tests, and evaluation against reviewed legal-document examples.
