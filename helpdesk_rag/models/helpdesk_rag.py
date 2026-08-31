import logging

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)


class HelpdeskRag(models.Model):
    _name = "helpdesk.rag"
    _description = "Documento del catálogo RAG de Helpdesk"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    # Readonly whenever there's a file (view attr: readonly="file") —
    # content is then owned by the OCR pipeline, not hand-edited. With no
    # file, a technician can paste text straight in and index that instead,
    # without ever going through a file.
    body = fields.Html()
    file = fields.Binary(string="Fichero", attachment=True, copy=False)
    file_name = fields.Char(string="Nombre del fichero", copy=False)

    rag_status = fields.Selection(
        [
            ("draft", "Pendiente"),
            ("sent", "Enviado"),
            ("indexed", "Indexado"),
            ("error", "Error"),
        ],
        default="draft",
        copy=False,
        tracking=True,
    )
    rag_sent_date = fields.Datetime(copy=False)
    rag_indexed_date = fields.Datetime(copy=False)
    rag_chunk_count = fields.Integer(default=0, copy=False)
    rag_error = fields.Text(copy=False)

    def action_rag_process(self):
        self.ensure_one()
        if not self.file and not self.body:
            return
        IrConfig = self.env["ir.config_parameter"].sudo()
        url = IrConfig.get_param("helpdesk_rag.n8n_ingest_url")
        if not url:
            self.write(
                {
                    "rag_status": "error",
                    "rag_error": "Falta el parámetro de sistema "
                    "'helpdesk_rag.n8n_ingest_url' "
                    "(Ajustes > Técnico > Parámetros > Parámetros del sistema).",
                }
            )
            return
        callback_token = IrConfig.get_param("helpdesk_rag.n8n_shared_secret")
        payload = {
            "record_id": self.id,
            "name": self.name,
            "token": callback_token,
        }
        if self.file:
            # Sent inline as base64 rather than a download link + token: the
            # file lives directly on this record (Binary field, no separate
            # ir.attachment the way attachment_id used to give us one), and
            # n8n needs the exact same base64 to hand to docling regardless
            # — skipping the extra fetch-it-back-from-Odoo round trip.
            file_data = self.file
            if isinstance(file_data, bytes):
                file_data = file_data.decode("ascii")
            payload.update(
                {
                    "source": "attachment",
                    "file_base64": file_data,
                    "file_name": self.file_name or "document.pdf",
                }
            )
        else:
            payload.update(
                {
                    "source": "body",
                    "body": self.body,
                }
            )
        # n8n acks immediately (responseMode=onReceived) and keeps OCR/
        # chunking/embedding running in the background — this timeout only
        # covers the ack, not the full pipeline.
        self.env.cr.commit()
        try:
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
            _logger.exception("Helpdesk RAG ingest failed for record %s", self.id)
            self.write({"rag_status": "error", "rag_error": str(exc)})

    def _rag_delete_vectors(self):
        if self.ids:
            self.env.cr.execute(
                "DELETE FROM helpdesk_rag_documentos WHERE record_id IN %s",
                (tuple(self.ids),),
            )

    def write(self, vals):
        if "file" in vals or ("body" in vals and "rag_status" not in vals):
            for record in self:
                record_vals = dict(vals)
                if "file" in vals and vals.get("file") != record.file:
                    record._rag_delete_vectors()
                    record_vals.setdefault("body", False)
                    record_vals.setdefault("file_name", False)
                    record_vals.setdefault("rag_status", "draft")
                    record_vals.setdefault("rag_error", False)
                    record_vals.setdefault("rag_chunk_count", 0)
                elif "body" in vals and "rag_status" not in vals:
                    record_vals["rag_status"] = "draft"
                super(HelpdeskRag, record).write(record_vals)
            return True
        return super().write(vals)

    def unlink(self):
        self._rag_delete_vectors()
        return super().unlink()
