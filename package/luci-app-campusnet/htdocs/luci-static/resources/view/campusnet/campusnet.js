'use strict';
'require view';
'require form';
'require uci';
'require rpc';

return view.extend({
	load: function() {
		return uci.load('campusnet');
	},

	render: function() {
		var m, s, o;

		m = new form.Map('campusnet', _('校园网自动登录'),
			_('配置校园网自动登录参数。'));

		s = m.section(form.TypedSection, 'config', _('基本设置'));
		s.anonymous = true;

		o = s.option(form.Flag, 'enabled', _('启用'),
			_('开启后，campusnet 将通过 cron 定时检查并自动登录。'));
		o.rmempty = false;

		o = s.option(form.Value, 'username', _('学号 / 上网账号'),
			_('你的校园网登录账号。'));
		o.placeholder = '20230001';
		o.rmempty = false;

		o = s.option(form.Value, 'wifi_ssid', _('校园 Wi-Fi 名称（SSID）'),
			_('填入校园网的 Wi-Fi 名称，换网后可自动切回。'));
		o.placeholder = 'JOU';

		o = s.option(form.ListValue, 'carrier', _('运营商'),
			_('登录前需要选择运营商的学校才需要设置。'));
		o.value('campus', _('校园用户'));
		o.value('cmcc', _('中国移动'));
		o.value('telecom', _('中国电信'));
		o.value('unicom', _('中国联通'));
		o.value('campus_telecom', _('电信校园网'));
		o.value('campus_unicom', _('联通校园网'));
		o.value('other', _('校园其他'));
		o.default = 'campus';

		o = s.option(form.Value, 'interval', _('检查间隔（分钟）'),
			_('cron 定时任务的执行间隔，默认 5 分钟。'));
		o.datatype = 'range(1, 60)';
		o.default = '5';

		return m.render();
	}
});
