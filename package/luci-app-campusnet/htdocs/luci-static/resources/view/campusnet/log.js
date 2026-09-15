'use strict';
'require view';
'require fs';
'require ui';

return view.extend({
	load: function() {
		return fs.exec('/usr/bin/logread', ['-e', 'campusnet']).then(function(res) {
			return res.stdout || '(暂无日志)';
		}).catch(function() {
			return '(读取日志失败)';
		});
	},

	render: function(logContent) {
		return E('div', { 'class': 'cbi-map' }, [
			E('h2', {}, _('校园网自动登录 - 运行日志')),
			E('div', { 'class': 'cbi-map-descr' },
				_('下方显示 campusnet 最近的运行日志（来自 syslog）。')),
			E('div', { 'class': 'cbi-section' }, [
				E('textarea', {
					'readonly': 'readonly',
					'rows': 30,
					'style': 'width: 100%; font-family: monospace; font-size: 12px;'
				}, logContent)
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
