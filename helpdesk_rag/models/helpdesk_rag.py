import logging

import psycopg2
import requests

from odoo import api, fields, models

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

    # --- Etiquetas para acotar la búsqueda -------------------------------
    # La búsqueda es puramente semántica y mezcla productos: ante "para qué
    # vale el botón de reproducción/pausa del macbook" se colaba una frase del
    # manual de un teclado Yamaha, porque hablaba de un botón PLAY/PAUSE. Estas
    # etiquetas son lo que permite acotar antes de buscar.
    scope = fields.Selection(
        [("customer", "Cliente"), ("internal", "Interno")],
        string="Ámbito",
        default="customer",
        required=True,
        tracking=True,
        help="Los documentos internos no deben aparecer en respuestas a clientes: "
        "un análisis de costes o un procedimiento propio no sale del equipo.",
    )
    manufacturer_id = fields.Many2one(
        "helpdesk.rag.manufacturer", string="Fabricante", tracking=True
    )
    model_ids = fields.Many2many(
        "helpdesk.rag.model",
        string="Modelos",
        help="Un mismo documento suele cubrir varios modelos: la guía de "
        "Samsung vale para el A57 y el A37.",
    )
    category = fields.Selection(
        [
            ("audio", "Audio e instrumentos"),
            ("it", "Informática"),
            ("mobile", "Móviles y tablets"),
            ("network", "Redes y comunicaciones"),
            ("other", "Otros"),
        ],
        string="Categoría",
        help="Filtro grueso para cuando el cliente no sabe el modelo exacto.",
    )
    document_type = fields.Selection(
        [
            ("manual", "Manual de usuario"),
            ("quickstart", "Guía rápida"),
            ("datasheet", "Ficha técnica"),
            ("procedure", "Procedimiento interno"),
            ("other", "Otro"),
        ],
        string="Tipo de documento",
        help="Permite dar preferencia al manual sobre material comercial.",
    )

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

    @api.onchange("manufacturer_id")
    def _onchange_manufacturer_id(self):
        # Igual que en el ticket: sin fabricante vale cualquier modelo; al
        # fijar uno, los de otras marcas dejan de tener sentido.
        if not self.manufacturer_id:
            return
        ajenos = self.model_ids.filtered(
            lambda m: m.manufacturer_id != self.manufacturer_id
        )
        if ajenos:
            self.model_ids -= ajenos

    @api.onchange("model_ids")
    def _onchange_model_ids(self):
        if self.manufacturer_id or not self.model_ids:
            return
        fabricantes = self.model_ids.mapped("manufacturer_id")
        if len(fabricantes) == 1:
            self.manufacturer_id = fabricantes

    def _rag_tags(self):
        """Etiquetas del documento, tal como se guardarán con cada vector.

        Las claves van en inglés porque son las que se consultan desde el SQL de
        n8n; las etiquetas visibles siguen en español.

        Los modelos van como lista y no como texto: un documento cubre varios
        (la guía de Samsung vale para el A57 y el A37) y el filtro tiene que
        acertar con cualquiera de ellos.
        """
        self.ensure_one()
        # El modelo ya dice de quién es el aparato: si falta el fabricante y
        # todos los modelos son de la misma marca, se deduce. Así el filtro por
        # fabricante sigue sirviendo aunque solo se hayan puesto modelos.
        manufacturer = self.manufacturer_id
        if not manufacturer:
            deducido = self.model_ids.mapped("manufacturer_id")
            manufacturer = deducido if len(deducido) == 1 else deducido.browse()
        nombres_modelo = self.model_ids.mapped("name")
        return {
            "document": self.name,
            "scope": self.scope,
            "manufacturer": manufacturer.name or None,
            # None y no [] a propósito: el SQL comprueba "documento sin modelos"
            # con IS NULL, y una lista vacía no es NULL. Con [] un documento
            # etiquetado solo por fabricante se caía de toda búsqueda que
            # filtrara por modelo, sin que nadie se enterara.
            "models": nombres_modelo or None,
            "category": self.category or None,
            "document_type": self.document_type or None,
        }

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
            # Las etiquetas viajan con el documento para que se guarden junto a
            # cada vector. No se pueden consultar después desde la búsqueda: los
            # vectores están en la base pgvector y este catálogo en la de Odoo,
            # que son bases distintas y no admiten un JOIN entre ellas.
            "tags": self._rag_tags(),
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
        """Borra del almacén RAG los vectores de estos registros.

        Los vectores viven en una tabla plana que llena n8n, no en un modelo
        Odoo. Esa tabla puede estar en OTRA base de datos —en el VPS pgvector
        corre aparte de la base de Odoo—, y entonces el cursor de Odoo no la
        ve. El DSN de esa base se pone en 'helpdesk_rag.vector_db_dsn'; sin ese
        parámetro se asume que comparten base, que es como corre en local.
        """
        if not self.ids:
            return
        sql = "DELETE FROM helpdesk_rag_documentos WHERE record_id IN %s"
        dsn = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("helpdesk_rag.vector_db_dsn")
        )
        if not dsn:
            self.env.cr.execute(sql, (tuple(self.ids),))
            return
        # Que esto falle deja vectores huérfanos, pero impedir que el usuario
        # borre el registro es peor: se deja constancia en el log y se sigue.
        conn = None
        try:
            conn = psycopg2.connect(dsn)
            with conn, conn.cursor() as cur:
                cur.execute(sql, (tuple(self.ids),))
        except Exception:
            _logger.exception(
                "No se pudieron borrar los vectores RAG de los registros %s",
                self.ids,
            )
        finally:
            if conn is not None:
                conn.close()

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
