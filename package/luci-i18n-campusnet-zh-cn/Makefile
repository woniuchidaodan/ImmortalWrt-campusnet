include $(TOPDIR)/rules.mk

PKG_NAME:=luci-i18n-campusnet-zh-cn
PKG_VERSION:=0.1.0
PKG_RELEASE:=1

PKG_LICENSE:=MIT
PKG_MAINTAINER:=demo133

# 关键：声明需要 luci-base 的 host 工具（其中包含 po2lmo）
PKG_BUILD_DEPENDS:=luci-base/host

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
endef

define Build/Compile
	@echo "Translation package - nothing to compile"
endef

define Package/luci-i18n-campusnet-zh-cn/install
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/i18n
	$(STAGING_DIR_HOST)/bin/po2lmo \
		$(CURDIR)/po/zh_Hans/campusnet.po \
		$(1)/usr/lib/lua/luci/i18n/campusnet.zh-cn.lmo
endef

$(eval $(call BuildPackage,luci-i18n-campusnet-zh-cn))
