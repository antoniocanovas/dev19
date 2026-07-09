{
    "name": "CRM Business - Knowledge Document Page",
    "version": "19.0.1.0.0",
    "summary": "Adds a procedure document page (OCA Document Page, no Enterprise dependency) to business lines, opportunities and quotations",
    "author": "Antonio Cánovas",
    "license": "AGPL-3",
    "category": "Sales/CRM",
    "depends": [
        "crm_business",
        "document_page",
    ],
    "data": [
        "views/crm_business_views.xml",
        "views/crm_lead_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
