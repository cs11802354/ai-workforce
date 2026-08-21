"""Worker-side view of the capability catalogues.

Mirrors backend/app/catalog.py, but adds the JSON Schemas the model needs in
order to call a tool. Kept as its own file because the worker image does not
depend on the backend package.
"""

SKILL_PROMPTS = {
    "web_search": "You can search the web for current information.",
    "calculator": "You are careful and precise with arithmetic and unit conversions.",
    "code_interpreter": "You can read, write, and reason about code.",
    "email_sender": "You can draft email. Always show a draft before sending.",
    "calendar": "You can read and propose calendar events.",
}

_TICKER = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Ticker, company name, or a plain-language request.",
        }
    },
    "required": ["query"],
}

_ARTIFACT_SPEC = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Document title."},
        "format": {
            "type": "string",
            "enum": ["html", "markdown", "pdf", "docx", "pptx"],
            "description": "Output format. Only html and markdown render live today.",
        },
        "sections": {
            "type": "array",
            "description": "Ordered document sections.",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["heading", "content"],
            },
        },
    },
    "required": ["title", "format", "sections"],
}

TOOL_SCHEMAS = {
    "bloomberg": {
        "name": "bloomberg",
        "description": "Query the Bloomberg Terminal for real-time pricing, market data, and news.",
        "input_schema": _TICKER,
    },
    "lseg_workspace": {
        "name": "lseg_workspace",
        "description": "Query LSEG Workspace (Refinitiv) for market data, filings, and analyst estimates.",
        "input_schema": _TICKER,
    },
    "factset": {
        "name": "factset",
        "description": "Query FactSet for company fundamentals, ownership, and screening.",
        "input_schema": _TICKER,
    },
    "capital_iq": {
        "name": "capital_iq",
        "description": "Query S&P Capital IQ for comparable companies, transactions, and credit data.",
        "input_schema": _TICKER,
    },
    "pitchbook": {
        "name": "pitchbook",
        "description": "Query PitchBook for private market, venture capital, and private equity deal data.",
        "input_schema": _TICKER,
    },
    "morningstar": {
        "name": "morningstar",
        "description": "Query Morningstar Direct for fund research, ratings, and performance.",
        "input_schema": _TICKER,
    },
    "aladdin": {
        "name": "aladdin",
        "description": "Query BlackRock Aladdin for portfolio construction and risk analytics.",
        "input_schema": _TICKER,
    },
    "sec_edgar": {
        "name": "sec_edgar",
        "description": "Look up SEC filings (10-K, 10-Q, 8-K, S-1) for a company.",
        "input_schema": _TICKER,
    },
    "artifact_generator": {
        "name": "artifact_generator",
        "description": (
            "Generate a document (HTML or Markdown) from a title and sections, "
            "store it, and return a stable URL. PDF/DOCX/PPTX are accepted but "
            "not yet connected."
        ),
        "input_schema": _ARTIFACT_SPEC,
    },
}

TOOL_DISPLAY_NAMES = {
    "bloomberg": "Bloomberg Terminal",
    "lseg_workspace": "LSEG Workspace",
    "factset": "FactSet",
    "capital_iq": "S&P Capital IQ",
    "pitchbook": "PitchBook",
    "morningstar": "Morningstar Direct",
    "aladdin": "BlackRock Aladdin",
    "sec_edgar": "SEC EDGAR",
    "artifact_generator": "Artifact Generator",
}


def anthropic_tools(tool_ids: list[str]) -> list[dict]:
    return [TOOL_SCHEMAS[t] for t in tool_ids if t in TOOL_SCHEMAS]


def openai_tools(tool_ids: list[str]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": TOOL_SCHEMAS[t]["name"],
                "description": TOOL_SCHEMAS[t]["description"],
                "parameters": TOOL_SCHEMAS[t]["input_schema"],
            },
        }
        for t in tool_ids
        if t in TOOL_SCHEMAS
    ]
