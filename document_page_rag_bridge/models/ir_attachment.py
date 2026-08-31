import logging

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)

RAW_CATEGORY_NAME = "raw"


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    rag_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("sent", "Enviado"),
            ("error", "Error"),
        ],
        default="pending",
        copy=False,
    )
    rag_sent_date = fields.Datetime(copy=False)
    rag_error = fields.Text(copy=False)

    def _rag_maybe_ingest(self):
        """Called by the 'RAG: ingest raw attachment' Automated Action.

        Only attachments hanging off a document.page whose category is
        'Raw' are sent onward; everything else (Wiki pages, other models)
        is left untouched.
        """
        for attachment in self:
            if attachment.res_model != "document.page":
                continue
            # The docling image-extraction branch (see /rag_bridge/upload_image)
            # attaches every extracted photo/diagram to this SAME raw page —
            # without this check, each image also matches "new attachment on
            # a raw page" and re-triggers the whole ingestion pipeline on
            # itself, treating a PNG as a manual to OCR/curate. Hit this for
            # real: a 132-page manual's images fanned out into 100+ spurious
            # re-ingestion attempts, all failing at the OCR step but still
            # burning real OpenRouter calls before failing.
            if (attachment.mimetype or "").startswith("image/"):
                continue
            page = self.env["document.page"].browse(attachment.res_id)
            if (
                not page.exists()
                or not page.parent_id
                or (page.parent_id.name or "").strip().lower() != RAW_CATEGORY_NAME
            ):
                continue
            # n8n fetches the attachment back from Odoo over a separate DB
            # connection as soon as it gets the webhook. Without committing
            # first, that connection can't see a row this transaction hasn't
            # committed yet — Postgres MVCC — and the download 404s even
            # though the attachment "exists".
            self.env.cr.commit()
            attachment._rag_send_to_n8n(page)

    def _rag_send_to_n8n(self, page):
        self.ensure_one()
        IrConfig = self.env["ir.config_parameter"].sudo()
        url = IrConfig.get_param("document_page_rag_bridge.n8n_ingest_url")
        if not url:
            self.write(
                {
                    "rag_status": "error",
                    "rag_error": "Falta el parámetro de sistema "
                    "'document_page_rag_bridge.n8n_ingest_url' "
                    "(Ajustes > Técnico > Parámetros > Parámetros del sistema).",
                }
            )
            return
        # Separate from web.base.url on purpose: that one is for links opened
        # in a human's browser. This is the URL n8n (a sibling container)
        # uses to pull the file back from Odoo over the Docker network, so
        # it must be the Docker service hostname, not localhost.
        base_url = IrConfig.get_param(
            "document_page_rag_bridge.odoo_internal_url", "http://odoo:8069"
        )
        # /web/content enforces normal ACLs, which the anonymous n8n request
        # would fail. _get_raw_access_token() is the scoped, stateless HMAC
        # token ir.binary._find_record checks first — unlike the legacy
        # generate_access_token() (a bare UUID), it matches the format
        # verify_limited_field_access_token expects, so it doesn't blow up
        # parsing it as a timestamp.
        token = self.sudo()._get_raw_access_token()
        payload = {
            "_model": "document.page",
            "page_id": page.id,
            "page_name": page.name,
            "attachment_id": self.id,
            "attachment_name": self.name,
            "mimetype": self.mimetype,
            "checksum": self.checksum,
            # Sent as separate fields, not one pre-built URL with a query
            # string: n8n's HTTP Request node (file/stream response mode)
            # was mangling an embedded querystring passed as a single
            # expression string. Letting it build the query itself avoids
            # the whole class of bug.
            "content_base_url": f"{base_url}/web/content/{self.id}",
            "access_token": token,
            "image_engine": self.env.company.rag_image_engine,
        }
        try:
            # n8n's Webhook trigger uses responseMode=onReceived: it acks
            # immediately and keeps processing (OCR, embeddings, curation)
            # in the background. This timeout is just for the ack itself —
            # it must NOT cover the full pipeline, or a real multi-hundred
            # page manual blocks the browser upload request for minutes.
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            self.write(
                {
                    "rag_status": "sent",
                    "rag_sent_date": fields.Datetime.now(),
                    "rag_error": False,
                }
            )
        except Exception as exc:
            _logger.exception(
                "RAG ingest failed for attachment %s (page %s)", self.id, page.id
            )
            self.write({"rag_status": "error", "rag_error": str(exc)})
