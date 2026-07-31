{
    "name": "Mercas MCP Chat",
    "version": "19.0.1.0.0",
    "summary": "Consola de chat con la IA (MCP Gateway) desde el propio backend de Odoo",
    "author": "Antonio Cánovas",
    "license": "LGPL-3",
    "category": "Productivity/AI",
    "depends": [
        "odoo_mcp_manager",
        "sale",
        "purchase",
        "account",
        "stock",
        "product_expiry",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ai_tool_sales_report.xml",
        "data/ai_tool_domain_reports.xml",
        "views/res_config_settings_views.xml",
        "wizard/ai_chat_wizard_views.xml",
        "wizard/ai_domain_chat_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mercas_mcp_chat/static/src/css/chat_fields.css",
            "mercas_mcp_chat/static/src/js/chat_fields.js",
            "mercas_mcp_chat/static/src/xml/chat_fields.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
}
