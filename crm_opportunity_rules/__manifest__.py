{
    "name": "CRM Opportunity Rules",
    "version": "19.0.1.0.0",
    "summary": "Suggest business opportunities from the client's profile and convert them into leads",
    "author": "Antonio Cánovas",
    "license": "LGPL-3",
    "category": "Sales/CRM",
    "depends": [
        "crm_partner_profile",
        "crm_business_product",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/crm_opportunity_suggestion_views.xml",
        "views/crm_opportunity_rule_views.xml",
        "views/crm_opportunity_rule_wizard_views.xml",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
