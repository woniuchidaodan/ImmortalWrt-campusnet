include $(TOPDIR)/rules.mk

PKG_NAME:=luci-i18n-campusnet-zh-cn
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_LICENSE:=MIT
PKG_MAINTAINER:=demo133

include $(INCLUDE_DIR)/package.mk

define Package/luci-i18n-campusnet-zh-cn
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=Translations
  TITLE:=Chinese (Simplified) translation for campusnet
  DEPENDS:=+luci-base +luci-app-campusnet
  PKGARCH:=all
endef

define Package/luci-i18n-campusnet-zh-cn/description
  Chinese (Simplified) translation for LuCI campusnet app.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./po $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(STAGING_DIR_HOST)/bin/po2lmo \
		$(PKG_BUILD_DIR)/po/zh_Hans/campusnet.po \
		$(PKG_BUILD_DIR)/campusnet.zh-cn.lmo
endef

define Package/luci-i18n-campusnet-zh-cn/install
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/i18n
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/campusnet.zh-cn.lmo \
		$(1)/usr/lib/lua/luci/i18n/campusnet.zh-cn.lmo
endef

$(eval $(call BuildPackage,luci-i18n-campusnet-zh-cn))
