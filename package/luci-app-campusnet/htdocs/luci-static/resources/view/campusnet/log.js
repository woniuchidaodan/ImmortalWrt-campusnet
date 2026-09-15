0
'use strict';
'require view';
'require fs';
'require ui';

return view.extend({
	load: function() {
		return fs.exec('/usr/bin/logread', ['-e', 'campusnet']).then(function(res) {
			return res.stdout || '';
		}).catch(function() {
			return '';
		});
	},

	render: function(logContent) {
		var text = logContent || '';

		if (!text) {
			text = '(暂无 campusnet 日志)\n\n' +
				'可能原因：\n' +
				'1. campusnet 还没有运行过\n' +
				'2. cron 任务还没有触发\n' +
				'3. 日志已被轮转\n\n' +
				'手动运行一次可产生日志：\n' +
				'  ssh root@路由器IP\n' +
				'  campusnet once';
		}

		return E('div', { 'class': 'cbi-map' }, [
			E('h2', {}, _('校园网自动登录 - 运行日志')),
			E('div', { 'class': 'cbi-map-descr' },
				_('下方显示 campusnet 最近的运行日志（来自 syslog）。')),
			E('div', { 'class': 'cbi-section' }, [
				E('textarea', {
					'readonly': 'readonly',
					'rows': 30,
					'style': 'width: 100%; font-family: monospace; font-size: 12px;'
				}, text)
			]),
			E('div', { 'class': 'cbi-page-actions' }, [
				E('button', {
					'class': 'btn cbi-button',
					'click': function() {
						window.location.reload();
					}
				}, _('刷新'))
			])
		]);
	}
});
