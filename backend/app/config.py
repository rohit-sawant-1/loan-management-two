"""
Settings for the app, read from the .env file.

Every other file that needs a setting imports `settings` from here instead of
reading environment variables itself. That way there is one place to see what
the app can be configured with, and .env.example stays accurate.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Where to find the .env file, relative to where the server is started
    # (which is always the backend/ folder).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Application ----
    app_name: str = "loan-application-management"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    # Keep a copy of the log on disk, so a reference number can still be looked
    # up tomorrow. Off during tests, where it would only make noise.
    log_to_file: bool = True
    log_dir: str = "logs"

    # ---- Program identity, goes into every log line ----
    poc_id: str = "POC-01"
    phase: int = 1
    associate_id: str = "unknown"

    # ---- Database ----
    database_url: str = "sqlite:///./loan_app.db"

    # ---- Security ----
    secret_key: str = "change-me"          # .env overrides this with a real one
    access_token_expire_hours: int = 24
    jwt_algorithm: str = "HS256"

    # ---- Front-end ----
    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173"

    # ---- OpenTelemetry ----
    otel_service_name: str = "poc-01-phase-1"
    # "console" prints every span to the terminal; "none" switches spans off (tests).
    otel_exporter: str = "console"

    # ---- The AI provider (Phase 2 onwards) ----
    # Which provider answers questions and makes embeddings: "gemini" or "ollama".
    # Gemini was blocked on the company network for six weeks and the whole
    # cohort had to move to Ollama, so this is one setting rather than a choice
    # baked into a dozen files.
    llm_provider: str = "gemini"

    # The models the trainer named — gemini-2.0-flash and models/text-embedding-004 —
    # have both been withdrawn by Google (T-51). These are the current
    # replacements, kept here so swapping them is one line in .env.
    #
    # This default must match what .env sets (T-69). It used to say
    # gemini-3.8-flash while .env said gemini-3.5-flash-lite, so anyone whose
    # .env was missing that one line would silently run a different, slower
    # model than the one chosen — and the one that was chosen was chosen for a
    # reason: gemini-3.5-flash-lite was the only model that survived the free
    # tier's rate limit without refusing (T-55).
    google_api_key: str = ""

    # Spare keys, comma-separated, tried in order after `google_api_key` runs
    # out of its daily quota. A free Gemini key has a small daily cap and one
    # Phase 5 review is several calls, so a single key empties fast. Borrowed
    # keys go here rather than replacing the one above, so the machine keeps
    # working if this line is left blank (D-20).
    #
    #     GOOGLE_API_KEYS=AIza...one,AIza...two
    google_api_keys: str = ""

    gemini_chat_model: str = "gemini-3.5-flash-lite"
    gemini_embed_model: str = "models/gemini-embedding-001"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1"
    ollama_embed_model: str = "nomic-embed-text"

    # ---- The vector store (Phase 2 onwards) ----
    chroma_persist_dir: str = "./chroma_db"
    # The trainer's ING-04 and RET-01 open this collection by its exact literal
    # name, so Gemini must use it unsuffixed. Only Ollama gets a suffix, which
    # is what keeps the two providers' vectors apart (T-46).
    chroma_collection: str = "poc_01_loan_manual"

    # ---- Retrieval settings, exactly as the Phase 2 spec fixes them ----
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k_results: int = 4

    # ---- LangSmith tracing ----
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "AI-Readiness-POC-01-P2"

    # ---- Phase 3 onwards: the agent's tools call the Phase 1 API over HTTP ----
    # Read directly from os.environ inside agent/tools.py rather than only
    # through this settings object, because the trainer's TC-01-P3-EXEC-06
    # patches the environment variable and reloads the module to prove the
    # tools notice a different API address. Kept here too so every other file
    # has one obvious place to look.
    api_base_url: str = "http://localhost:8000"

    # The agent calls the Phase 1 API as a real signed-in user, not as itself,
    # because every endpoint is owner-scoped and role-checked (Rule 6, D-06).
    # Rather than store a token that expires in 24 hours and quietly breaks the
    # demo the next day, the agent mints a fresh one from this email each time
    # it starts (see agent/tools.py). It answers with a branch manager's view,
    # since Phase 3's tools are read-only and a manager can read everything.
    agent_service_email: str = "anita@bank.com"

    @property
    def cors_origin_list(self) -> list[str]:
        """The CORS setting as a Python list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
