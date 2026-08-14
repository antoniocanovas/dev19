from odoo import http
from odoo.http import request
from odoo.addons.web.controllers import home as web_home


class Home(web_home.Home):

    @http.route(
        '/web/login/single_session',
        type='http', auth='public', methods=['GET', 'POST'], sitemap=False,
        website=True, multilang=False,
    )
    def web_single_session(self, redirect=None, **kwargs):
        if request.session.uid:
            return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))

        pre_uid = request.session.get('pre_uid')
        if not pre_uid:
            return request.redirect('/web/login')

        user = request.env['res.users'].browse(pre_uid)
        error = None

        if request.httprequest.method == 'POST':
            other_devices = user._get_other_active_devices()
            if kwargs.get('revoke_all'):
                other_devices._revoke()
            elif kwargs.get('revoke_device_id'):
                device = other_devices.filtered(lambda d: d.id == int(kwargs['revoke_device_id']))
                device._revoke()
            else:
                error = "Acción no reconocida."

        devices = user._get_other_active_devices()
        if not devices and not error:
            request.session.finalize(request.env)
            request.update_env(user=request.session.uid)
            request.update_context(**request.session.context)
            return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))

        return request.render('user_single_session.single_session_form', {
            'user': user,
            'devices': devices,
            'redirect': redirect,
            'error': error,
        })
