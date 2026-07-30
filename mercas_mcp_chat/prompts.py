"""Business-domain instructions injected into the 'Consultas IA' classification
prompt (wizard/ai_domain_chat_wizard.py). Kept in its own module (not a DB
field) so it stays under version control and cannot be edited away by mistake
from the UI — the editable counterpart lives in res.config.settings as
mercas_mcp_chat.custom_instructions."""

BASE_BUSINESS_INSTRUCTIONS = (
    'INSTRUCCIONES DE NEGOCIO (fijas):\n'
    '- Si el usuario pregunta por un producto, cliente o proveedor concreto, la respuesta '
    'debe ceñirse exclusivamente a ese producto/cliente/proveedor: no mezcles cifras de '
    'otros productos ni de otros clientes/proveedores en el resultado.\n'
    '- Si el usuario pregunta por "cajas" o "envases", NO se refiere a un producto que se '
    'llame así, sino a los productos marcados como envase/caja retornable '
    '(campo is_box = True). En ese caso, en el dominio "stock" pon "only_boxes": true y deja '
    '"product" vacío, salvo que además mencione un producto concreto.\n'
)
