include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI app for campusnet — campus network auto-login
LUCI_DEPENDS:=+luci-base +campusnet
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

define Package/luci-app-campusnet/install
	$(call Package/luci-app-campusnet/install/default,$(1))

	# 1. 默认 UCI 配置（IPK 直接携带）
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/campusnet.config $(1)/etc/config/campusnet

	# 2. uci-defaults 补救脚本
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/luci-app-campusnet.defaults $(1)/etc/uci-defaults/luci-app-campusnet

	# 3. config-sync 同步脚本
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) ./files/campusnet-config-sync $(1)/usr/libexec/campusnet-config-sync
endef

$(eval $(call BuildPackage,luci-app-campusnet))
