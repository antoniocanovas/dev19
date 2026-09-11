{
    "name": "Helpdesk RAG",
    "summary": "Catálogo de documentos RAG para Helpdesk, indexado con modelos locales (Ollama)",
    "version": "19.0.1.3.0",
    "license": "AGPL-3",
    "author": "Inforges",
    "category": "Helpdesk",
    "depends": ["helpdesk_mgmt", "mail", "ai_oca_bridge"],
    "data": [
        "security/ir.model.access.csv",
        "views/helpdesk_rag_views.xml",
        "views/helpdesk_ticket_views.xml",
    ],
}