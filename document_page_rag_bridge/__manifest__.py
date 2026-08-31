{
    "name": "Document Page RAG Bridge",
    "summary": "Envía a n8n para ingesta RAG los adjuntos subidos bajo la categoría 'Raw' de Knowledge",
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "author": "Inforges",
    "category": "AI",
    "depends": ["document_page", "base_automation", "document_page_reference"],
    "data": [
        "data/automation.xml",
        "views/document_page.xml",
        "views/res_company.xml",
    ],
}
