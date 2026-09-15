include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI app for campusnet — campus network auto-login
LUCI_DEPENDS:=+luci-base +campusnet
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

# 显式安装可执行脚本，强制 755 权限（绕过 GitHub 网页丢失 +x 的问题）
define Package/luci-app-campusnet/install
	$(call Package/luci-app-campusnet/install/default,$(1))
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/luci-app-campusnet.defaults $(1)/etc/uci-defaults/luci-app-campusnet
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) ./files/campusnet-config-sync $(1)/usr/libexec/campusnet-config-sync
endef

$(eval $(call BuildPackage,luci-app-campusnet))
