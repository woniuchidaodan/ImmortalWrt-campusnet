'use strict';
'require view';
'require form';
'require uci';
'require rpc';
'require fs';
'require ui';

return view.extend({
	load: function() {
		return uci.load('campusnet');
	},

	render: function() {
		var m, s, o;

		m = new form.Map('campusnet', _('校园网自动登录'),
			_('配置校园网自动登录参数。认证系统会自动识别，无需手动指定。'));

		s = m.section(form.TypedSection, 'config', _('基本设置'));
		s.anonymous = true;

		o = s.option(form.Flag, 'enabled', _('启用'),
			_('开启后，campusnet 将通过 cron 定时检查并自动登录。'));
		o.rmempty = false;

		o = s.option(form.Value, 'username', _('校园网登录账号'),
			_('通常为学号，也可能是手机号、工号或学校分配的其他账号。'));
		o.placeholder = '20230001';
		o.rmempty = false;

		o = s.option(form.Value, 'password', _('密码'),
			_('校园网登录密码。保存在 /etc/campusnet.env（权限 0600）。'));
		o.password = true;
		o.rmempty = true;

		o = s.option(form.Value, 'wifi_ssid', _('校园 Wi-Fi 名称（SSID）'),
			_('填入校园网的 Wi-Fi 名称，换网后可自动切回。'));
		o.placeholder = 'JOU';

		o = s.option(form.ListValue, 'carrier', _('运营商'),
			_('默认“自动识别”即可，campusnet 会探测门户页面判断。'));
		o.value('auto', _('自动识别'));
		o.value('campus', _('校园用户'));
		o.value('cmcc', _('中国移动'));
		o.value('telecom', _('中国电信'));
		o.value('unicom', _('中国联通'));
		o.value('campus_telecom', _('电信校园网'));
		o.value('campus_unicom', _('联通校园网'));
		o.value('other', _('校园其他'));
		o.default = 'auto';

		o = s.option(form.Value, 'interval', _('检查间隔（分钟）'),
			_('cron 定时任务的执行间隔，默认 5 分钟。'));
		o.datatype = 'range(1, 60)';
		o.default = '5';

		o = s.option(form.Value, 'timeout', _('请求超时（秒）'),
			_('单次认证请求的超时时间，默认 10 秒。'));
		o.datatype = 'range(3, 60)';
		o.default = '10';

		var origSave = m.save;
		m.save = function() {
			return origSave.apply(this, arguments).then(function() {
				return fs.exec('/usr/libexec/campusnet-config-sync');
			});
		};

		return m.render();
	}
});