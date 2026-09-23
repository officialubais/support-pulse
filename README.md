# SupportPulse — AI-Powered Customer Support & Product Media Agent

SupportPulse is an intelligent, multi-modal customer support agent built with the **Agent Development Kit (ADK)** and deployed on **Google Cloud Agent Runtime**. It seamlessly combines real-time order tracking, database inventory management, AI product preview image generation, and promotional video generation powered by Google's Omni model (`gemini-omni-flash-preview`).

![SupportPulse Demo](./demo.gif)

---

## 🚀 Key Implemented Capabilities

SupportPulse implements the following production features strictly wired in code:

* **📦 Firestore Order Tracking (`lookup_order_details`)**: Queries Google Cloud Firestore (`orders` collection) to retrieve real-time order status, carrier info, tracking numbers, and delivery dates (with built-in local fallback support).
* **📊 Firestore Inventory Lookup (`check_inventory_stock`)**: Queries Firestore (`products` collection) to check product stock counts, warehouse locations, and restock schedules by SKU.
* **🎨 AI Product Image Generation (`generate_product_preview_image`)**: Utilizes Google GenAI SDK with **Imagen 3** (`imagen-3.0-generate-002`) to generate studio-quality product visual previews.
* **🎥 Omni Video Generation & Cloud Storage (`generate_product_item_video`)**: Leverages Google's Omni model (**`gemini-omni-flash-preview`** in `global` region) via Vertex AI Interactions API to generate promotional product videos. Videos are registered to the ADK Artifacts panel (`tool_context.save_artifact`) and uploaded to a public **Google Cloud Storage (GCS)** bucket (`support-pulse-assets...`).
* **🧠 Persistent Memory Bank (`VertexAiMemoryBankService`)**: Uses Vertex AI Memory Bank for long-term cross-session user memory storage, loading, and context preloading (`load_memory`, `preload_memory`).
* **📱 Visual A2UI Components**: Includes a custom A2UI callback (`a2ui_callback`) and catalog manager (`BasicCatalog`) to render visual UI widgets like interactive order status progress steppers (*Placed ➔ Processing ➔ In Transit 🚚 ➔ Delivered 📦*).
* **🖥️ Custom Responsive Chat Web Interface**: A lightweight FastAPI web proxy and single-page UI (`./frontend`) supporting dark/light mode toggle, interactive starter prompt pills, image lightboxes, native embedded `<video controls autoplay loop muted>` players, auto-scrolling, and transcript export (`📥`).

---

## 📋 Feature Implementation Status

| Feature | Status | Technology / Service |
| :--- | :--- | :--- |
| Real-time Order Tracking | **Implemented** | Google Cloud Firestore / Custom ADK Tool |
| Inventory Stock Query | **Implemented** | Google Cloud Firestore / Custom ADK Tool |
| Product Preview Image Generation | **Implemented** | Imagen 3 (`imagen-3.0-generate-002`) / GenAI SDK |
| Promotional Video Generation | **Implemented** | Google Omni (`gemini-omni-flash-preview`) / Vertex AI |
| Public Video Storage | **Implemented** | Google Cloud Storage (GCS) Public Bucket |
| Cross-Session User Memory | **Implemented** | Vertex AI Memory Bank Service |
| Visual Component Stepper | **Implemented** | A2UI Framework & Catalog Callback |
| Standalone Web Chat Interface | **Implemented** | FastAPI Proxy + HTML5/CSS3 Single Page App |
| Automated Refund Processing | *Planned (Not implemented)* | Requires External Payment Gateway API |
| Live Human Agent Handoff | *Planned (Not implemented)* | Requires WebSocket Queueing System |

---

## 🏗️ Project Architecture

```text
support-pulse/
├── app/                        # Core Agent Application
│   ├── agent.py                # Agent logic, tools, Firestore, GCS & Omni video integration
│   ├── a2ui_utils.py           # A2UI callback and component catalog manager
│   ├── fast_api_app.py         # Agent FastAPI entrypoint
│   └── app_utils/              # Shared helper functions
├── frontend/                   # Plain Web Chat Frontend & Proxy
│   ├── main.py                 # FastAPI proxy server for A2A protocol
│   ├── Dockerfile              # Container definition for frontend service
│   ├── requirements.txt        # Frontend dependencies
│   └── static/
│       └── index.html          # Responsive single-page UI (A2UI & Media renderer)
├── demo.gif                    # Inline demonstration recording
├── record_demo.py              # Playwright automated demo recording script
├── add_music_to_demo.py        # Audio-video dubbing script (static-ffmpeg)
├── generate_lofi_music.py      # Lo-fi music synthesizer script
├── agents-cli-manifest.yaml    # Agents CLI manifest configuration
└── pyproject.toml              # Python project dependencies (uv)
```

---

## 🛠️ Local Development & Setup

### Prerequisites

Ensure you have the following installed on your environment:

* **Python**: 3.11+
* **uv**: Python package manager (`pip install uv` or follow [astral.sh/uv](https://docs.astral.sh/uv/))
* **google-agents-cli**: Installed via `uv tool install google-agents-cli`
* **Google Cloud SDK**: `gcloud` authenticated with access to Vertex AI, Firestore, and GCS.

### 1. Environment Configuration

Copy the example environment file and set your target Google Cloud credentials and resource names:

```bash
cp .env.example .env
```

Key environment variables in `.env`:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_ENGINE_RESOURCE_NAME=projects/your-project-id/locations/us-central1/reasoningEngines/your-engine-id
AGENT_DIRECTORY=app
```

### 2. Installing Dependencies

Install project dependencies using `uv`:

```bash
uv sync
```

### 3. Running the Agent Locally (ADK Web Playground)

To test the agent core with the official ADK web interface and auto-reloading:

```bash
GOOGLE_GENAI_USE_VERTEXAI=true uv run adk web app --port 8080 --reload_agents
```

### 4. Running the Custom Frontend Server

To run the dedicated SupportPulse chat web interface locally:

```bash
cd frontend
uv run python main.py
```

Or using Uvicorn directly:

```bash
uv run uvicorn frontend.main:app --host 0.0.0.0 --port 8080
```

---

## 🐳 Docker Deployment

To build and run the frontend container locally or prepare for containerized deployment:

```bash
# Build the Docker image
docker build -t support-pulse-frontend ./frontend

# Run the container
docker run -d -p 8080:8080 \
  -e AGENT_ENGINE_RESOURCE_NAME="projects/your-project-id/locations/us-central1/reasoningEngines/your-engine-id" \
  -e AGENT_DIRECTORY="app" \
  support-pulse-frontend
```

---

## 🧪 Testing

Run unit tests and verification suites:

```bash
uv run pytest tests/
```

---

## 📄 License

Apache License 2.0. See `LICENSE` for details.
