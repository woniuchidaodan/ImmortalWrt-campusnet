#
# campusnet — OpenWrt/ImmortalWrt package definition
#
include $(TOPDIR)/rules.mk

PKG_NAME:=campusnet
PKG_VERSION:=0.1.0
PKG_RELEASE:=1

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/demo133/campusnet.git
PKG_SOURCE_VERSION:=acfbff491a49a9b3dac77fe550cb1d5201513afe
PKG_MIRROR_HASH:=df0de5aac893a073890f52e8464162fe5860dd74811ee0f8b1a8ed9589f5f2a8
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

$(eval $(call Py3Package,campusnet))
$(eval $(call BuildPackage,campusnet))
$(eval $(call BuildPackage,campusnet-src))
