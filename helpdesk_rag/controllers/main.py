import json
import logging

from markupsafe import Markup, escape
from werkzeug.exceptions import Forbidden, NotFound

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)

# Página mínima para el visor: el documento ya trae su propio marcado, aquí
# solo se envuelve. Las imágenes van embebidas como data-URI y algunas son más
# anchas que la pantalla, de ahí el max-width.
_PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>%(titulo)s</title>
<style>
 body { max-width: 60rem; margin: 2rem auto; padding: 0 1rem;
        font-family: system-ui, -apple-system, sans-serif; line-height: 1.5; }
 img { max-width: 100%%; height: auto; }
 table { border-collapse: collapse; } td, th { border: 1px solid #ccc; padding: .25rem .5rem; }
 :target { background: #fff3cd; }
</style>
</head>
<body>
<h1>%(titulo)s</h1>
%(cuerpo)s
</body>
</html>"""


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
        "/helpdesk_rag/doc/<int:doc_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def document_html(self, doc_id, **kwargs):
        """Sirve el documento como página HTML propia, para usuarios con sesión.

        Las respuestas de la IA enlazan a la sección concreta con un
        '#seccion-...'. Abrir la ficha del backend no sirve para eso: Odoo monta
        el formulario por JavaScript DESPUÉS de que el navegador haya procesado
        el fragmento, así que no hay nada a lo que saltar y el enlace deja al
        usuario al principio de un documento de cientos de páginas. Servido como
        página estática, el anclaje del navegador funciona sin más.
        """
        # Sin sudo a propósito: leer con el env del usuario aplica sus permisos
        # y reglas de registro, que es justo el control de acceso que se quiere.
        record = request.env["helpdesk.rag"].browse(doc_id).exists()
        if not record:
            raise NotFound()
        try:
            titulo = record.name
            cuerpo = record.body
        except AccessError as exc:
            raise Forbidden() from exc

        if not cuerpo:
            cuerpo = Markup("<p><em>Este documento todavía no tiene contenido.</em></p>")

        pagina = _PLANTILLA % {
            "titulo": escape(titulo or ""),
            # El campo es fields.Html, que Odoo sanea al guardarlo; se inserta
            # tal cual porque es justo el marcado que hay que mostrar.
            "cuerpo": cuerpo,
        }
        return request.make_response(
            pagina,
            headers=[
                ("Content-Type", "text/html; charset=utf-8"),
                # Documentación interna: que no la cachee ningún proxy.
                ("Cache-Control", "private, max-age=0"),
            ],
        )

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
