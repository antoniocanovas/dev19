import json
import logging

from odoo import fields, http
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


def _check_token(data):
    expected = (
        request.env["ir.config_parameter"]
        .sudo()
        .get_param("helpdesk_rag.n8n_shared_secret")
    )
    return expected and consteq(data.get("token") or "", expected)


def _error(message, status=403):
    return request.make_response(
        json.dumps({"error": message}),
        status=status,
        headers=[("Content-Type", "application/json")],
    )


class HelpdeskRagController(http.Controller):
    @http.route(
        "/helpdesk_rag/set_result",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def set_result(self, **kwargs):
        """Called by n8n once OCR (docling + ministral-3 vision) + chunking
        + embedding (qwen3-embedding) finishes for one helpdesk.rag record.

        Vectors themselves are inserted directly into helpdesk_rag_documentos
        by n8n (plain SQL table, not an Odoo model — same pattern as the
        Knowledge-based pipeline's rag_documentos) — this endpoint only
        writes the human-facing side: the transcribed body and final status.

        Body: {token, record_id, body?, chunk_count?, status?, error?}
        Response: {ok: true}
        """
        data = json.loads(request.httprequest.get_data() or b"{}")
        if not _check_token(data):
            return _error("invalid or missing token")

        record_id = data.get("record_id")
        if not record_id:
            return _error("missing record_id", status=400)

        Rag = request.env["helpdesk.rag"].sudo()
        record = Rag.browse(int(record_id))
        if not record.exists():
            return _error("record_id not found", status=404)

        vals = {"rag_status": data.get("status") or "indexed"}
        if data.get("body") is not None:
            vals["body"] = data["body"]
        if data.get("chunk_count") is not None:
            vals["rag_chunk_count"] = data["chunk_count"]
        if data.get("error") is not None:
            vals["rag_error"] = data["error"]
        if vals["rag_status"] == "indexed":
            vals["rag_indexed_date"] = fields.Datetime.now()
        record.write(vals)
        return request.make_response(
            json.dumps({"ok": True}), headers=[("Content-Type", "application/json")]
        )
