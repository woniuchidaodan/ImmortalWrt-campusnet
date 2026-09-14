include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI app for campusnet — campus network auto-login
LUCI_DEPENDS:=+luci-base +campusnet
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
$(eval $(call BuildPackage,luci-app-campusnet))
