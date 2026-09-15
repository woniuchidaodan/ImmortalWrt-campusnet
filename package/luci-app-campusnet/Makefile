include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI app for campusnet — campus network auto-login
LUCI_DEPENDS:=+luci-base +campusnet
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

# 全部显式安装，不依赖 luci.mk 的 install/default 宏
define Package/luci-app-campusnet/install
	# 1. 前端 JS（关键：显式装到 /www/）
	$(INSTALL_DIR) $(1)/www/luci-static/resources/view/campusnet
	$(INSTALL_DATA) ./htdocs/luci-static/resources/view/campusnet/campusnet.js \
		$(1)/www/luci-static/resources/view/campusnet/campusnet.js
	$(INSTALL_DATA) ./htdocs/luci-static/resources/view/campusnet/log.js \
		$(1)/www/luci-static/resources/view/campusnet/log.js

	# 2. 菜单
	$(INSTALL_DIR) $(1)/usr/share/luci/menu.d
	$(INSTALL_DATA) ./root/usr/share/luci/menu.d/luci-app-campusnet.json \
		$(1)/usr/share/luci/menu.d/luci-app-campusnet.json

	# 3. ACL
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./root/usr/share/rpcd/acl.d/luci-app-campusnet.json \
		$(1)/usr/share/rpcd/acl.d/luci-app-campusnet.json

	# 4. 默认 UCI 配置
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/campusnet.config $(1)/etc/config/campusnet

	# 5. uci-defaults
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/luci-app-campusnet.defaults $(1)/etc/uci-defaults/luci-app-campusnet

	# 6. config-sync 脚本
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) ./files/campusnet-config-sync $(1)/usr/libexec/campusnet-config-sync
endef

$(eval $(call BuildPackage,luci-app-campusnet))
