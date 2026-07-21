# Mercas AI

Asistente de IA para el mercado mayorista de frutas y hortalizas: responde preguntas en
lenguaje natural sobre cajas en depósito, trazabilidad de lotes y ventas, consultando en
vivo la base de datos de Odoo. Corre sobre un modelo Ollama local (gemma4 por defecto), sin
enviar datos a ningún servicio externo.

Este módulo no añade modelos ni vistas propias: solo registra un **agente** (`muk_ai.agent`)
preconfigurado sobre la infraestructura de chat/tool-calling que ya aportan `muk_ai` y
`muk_mcp`.

## Dependencias

| Módulo | Para qué |
|---|---|
| `mercas_base` | Aporta los campos de dominio que el agente consulta: `res.partner.mercas_box_qty` (cajas en depósito) y, vía `sale_order_lot_selection`, `sale.order.line.lot_id` (trazabilidad de lotes). |
| `muk_ai_ollama` | Arrastra transitivamente `muk_ai` (el chat) y `muk_mcp` (el registro de herramientas MCP: `search_read`, `read_group`, etc.) y añade el proveedor Ollama. |

## Qué instala

Un único registro `muk_ai.agent` llamado **"Mercas"** (`data/muk_ai_agent.xml`), independiente
del "Asistente general" de MuK — no lo modifica ni lo sustituye.

- **Modelo**: `Gemma 4` (`gemma4:latest`) sobre el proveedor Ollama, referenciado directamente
  (`muk_ai_ollama.model_gemma4`). No depende del modelo por defecto global del proveedor, así
  que cambiar ese default no afecta a este agente.
- **Solo lectura** (`read_only = True`): no puede ejecutar `create_records` / `update_records`
  / `delete_records` / `call_method`, solo herramientas de consulta.
- **Herramientas**: `search_read`, `search_count`, `read_group`, `read_records`, `ask_user` van
  con el esquema completo desde el primer turno (`essential_tool_names`); `describe_model` está
  permitida pero se carga bajo demanda (`tool_filter`) para no engordar el prompt inicial si no
  hace falta.
- **Prompt**: incluye un glosario de negocio con las recetas de consulta exactas para las
  preguntas típicas (cajas de un cliente, ventas de un lote, clientes de un lote) y unas reglas
  de velocidad (máximo 3 llamadas a herramienta por pregunta, `fields`/`limit` siempre
  explícitos, sin preámbulo) pensadas para un modelo local: cada llamada a herramienta cuesta
  latencia real, así que el objetivo es que razone lo mínimo imprescindible.
- **Handoff**: `allow_handoff = True`, así que el agente Router de MuK puede derivar aquí
  preguntas que reconozca como de este dominio.
- 3 sugerencias de arranque en el chat vacío, con las preguntas que motivaron el módulo:
  - "¿Cuántas cajas tiene en su almacén Cliente1?"
  - "¿Cuándo vendí el lote 000001 a Cliente1?"
  - "¿A qué clientes he vendido el lote 1 de lechugas?"

## Configuración de Ollama

No requiere pasos adicionales si Ollama corre en `http://localhost:11434` (valor por defecto
de `muk_ai_ollama`) y el modelo `gemma4:latest` ya está descargado (`ollama pull gemma4`).

Si Ollama corre en otra máquina o puerto, se cambia en **Ajustes → sección AI → Ollama Base
URL** — es una configuración global del proveedor, no de este módulo.

## Editar el prompt o las herramientas permitidas

Desde **MuK AI → Agents → Mercas**, pestaña "System Prompt". El registro se carga con
`noupdate="1"`, así que los cambios hechos desde la UI no se pierden al actualizar el módulo.
Para cambios versionados, editar `data/muk_ai_agent.xml`.

## Ampliar el glosario de negocio

Si se añaden nuevos casos de uso (por ejemplo, consultas sobre liquidaciones o márgenes de
lote), lo más económico es añadir la receta de dominio directamente al `system_prompt` en vez
de depender de que el modelo descubra el esquema con `describe_model` en cada conversación —
es la diferencia entre 1 y 3 llamadas a herramienta por pregunta con un modelo local.
