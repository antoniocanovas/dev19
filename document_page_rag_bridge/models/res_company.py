from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Testing/comparison switch: OpenRouter's mistral-ocr file-parser plugin
    # can also return images, but OpenRouter hard-caps it at 8 per PDF
    # (non-configurable) regardless of how many the document actually has -
    # fine for a short flyer, useless for a 100+ page manual. docling has no
    # such cap (only our own size filter). Default stays docling; this field
    # exists to A/B the two without editing the n8n workflow each time.
    rag_image_engine = fields.Selection(
        [
            ("docling", "Docling (sin límite de imágenes)"),
            ("openrouter", "OpenRouter / Mistral OCR (máx. 8 imágenes por PDF)"),
        ],
        string="Motor de extracción de imágenes RAG",
        default="docling",
        required=True,
    )
