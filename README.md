# Enterprise Ticket Resolution Assistant

An AI-powered Retrieval-Augmented Generation (RAG) system that generates reusable ticket resolution workflows by leveraging historical resolved incidents.

The system retrieves similar historical tickets from a vector database, uses a Large Language Model (LLM) to generate generalized resolution workflows, and exposes the functionality through a FastAPI backend and Streamlit frontend.

---

## Features

- Historical ticket retrieval using ChromaDB
- Semantic search using Qwen embeddings
- Resolution workflow generation using Groq LLMs
- Confidence-based response filtering
- FastAPI REST API backend
- Streamlit frontend interface
- Structured output generation
- Source ticket traceability
- Evaluation framework for measuring workflow quality

---

## Architecture

```text
User Query
     │
     ▼
Streamlit Frontend
     │
     ▼
FastAPI Backend
     │
     ▼
Inference Pipeline
     │
     ├── Generate Embedding
     │
     ├── ChromaDB Retrieval
     │
     ├── Context Construction
     │
     ├── Groq LLM Generation
     │
     └── Confidence Validation
     │
     ▼
Generated Resolution Workflow
```

---

## Technology Stack

### Backend

- FastAPI
- Pydantic
- LangChain
- Groq API

### Retrieval

- ChromaDB
- Sentence Transformers
- Qwen/Qwen3-Embedding-0.6B

### Frontend

- Streamlit

### Database

- MySQL

### Evaluation

- Custom Evaluation Framework
- Groq-based Workflow Assessment

---

## Project Structure

```text
project/
│
├── api.py                     # FastAPI backend
├── app.py                     # Streamlit frontend
├── inference.py               # RAG inference pipeline
├── prompt.py                  # LLM prompts
├── schemas.py                 # Structured response schemas
├── config.py                  # Configuration settings
│
├── evaluation/
│   ├── inference_eval.py
│   ├── groq_evaluation.py
│   ├── generate_ragas_dataset.py
│   └── eval_config.py
│
├── chroma_db/
│
├── .env
├── .env_example
├── requirements.txt
│
└── README.md
```

---

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/Swastigit2005/Service-ticket-resolver.git
cd Service-ticket-resolver
```

---

### 2. Create Virtual Environment

```bash
python -m venv venv
```

Activate:

#### Windows

```bash
venv\Scripts\activate
```

#### Linux / Mac

```bash
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key

MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=ticket_system
```

---

### 5. Start Backend

```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

API available at:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

---

### 6. Start Frontend

```bash
streamlit run app.py
```

Frontend available at:

```text
http://localhost:8501
```

---

## API Endpoint

### POST `/resolve`

Request:

```json
{
  "issue": "I need assistance locating a doctor who participates in my insurance network."
}
```

Response:

```json
{
  "resolution_steps": [
    "Verify the customer's plan and network details.",
    "Check provider directory resources.",
    "Confirm provider participation.",
    "Identify alternate in-network providers if needed."
  ],
  "source_tickets": [
    {
      "ticket_id": "INC5044680",
      "similarity_distance": 0.7635
    }
  ]
}
```

---

## Evaluation

The project includes an evaluation framework for measuring:

- Correctness
- Completeness
- Groundedness
- Generalization
- Relevance
- Overall Quality

Evaluation is performed using a separate inference pipeline and Groq-based scoring.

---

## Confidence Filtering

The backend applies a confidence threshold before returning a response.

If confidence falls below the configured threshold:

```json
{
  "resolution_steps": "",
  "source_tickets": []
}
```

This prevents low-confidence recommendations from reaching the frontend.

---

## Future Enhancements

- User authentication
- Multi-user support
- Docker deployment
- CI/CD integration
- Monitoring and logging
- Feedback collection system
- Human-in-the-loop validation

---

## Author

**Swasti**

Enterprise Ticket Resolution Assistant – RAG-based Workflow Generation System
