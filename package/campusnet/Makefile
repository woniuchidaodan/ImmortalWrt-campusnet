#
# campusnet — OpenWrt/ImmortalWrt package definition
#
include $(TOPDIR)/rules.mk

PKG_NAME:=campusnet
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/demo133/campusnet.git
PKG_SOURCE_VERSION:=acfbff491a49a9b3dac77fe550cb1d5201513afe
PKG_MIRROR_HASH:=d642e1c9c75f1083d93e19ff550cfa73663d0411928fcf4dc6b2da02e0dec69f
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKG_MAINTAINER:=demo133

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-package.mk

define Package/campusnet
  SECTION:=utils
  CATEGORY:=Utilities
  SUBMENU:=Network
  TITLE:=Campus network portal auto-login CLI
  DEPENDS:=+python3-light
  VARIANT:=python3
endef

define Package/campusnet/description
  Zero-dependency CLI tool for campus network portal auto-login.
  Supports Dr.COM, Srun, Ruijie, and Huawei eportal authentication.
  Works on OpenWrt with procd + cron.
endef

define Build/Compile
	$(call Build/Compile/Py3Mod,., \
		install --prefix="/usr" --root="$(PKG_INSTALL_DIR)" \
	)
endef

define Package/campusnet/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/campusnet $(1)/usr/bin/
endef

$(eval $(call BuildPackage,campusnet))
