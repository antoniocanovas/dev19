def post_init_hook(env):
    """Activa, tal y como lo haría un usuario marcando las casillas en
    Inventario > Configuración > Ajustes y guardando, las opciones:
    - Almacén: Ubicaciones de almacenamiento
    - Trazabilidad: Números de serie y lote
    - Productos: Variantes
    - Productos: Unidades de medida y embalajes
    - Firma (pide firma en las órdenes de entrega)

    Se hace instanciando y ejecutando `res.config.settings` (en vez de tocar
    directamente `implied_ids`) porque varios de estos ajustes disparan lógica
    adicional en su `set_values()` (p. ej. `stock` activa/desactiva tipos de
    operación de los almacenes al tocar `group_stock_multi_locations`, y el
    grupo de `group_stock_production_lot` también se aplica a `base.group_portal`,
    no solo a `base.group_user`).
    """
    env["res.config.settings"].create(
        {
            "group_stock_multi_locations": True,
            "group_stock_production_lot": True,
            "group_product_variant": True,
            "group_uom": True,
            "group_stock_sign_delivery": True,
        }
    ).execute()
