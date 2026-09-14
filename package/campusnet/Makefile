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
PKG_MIRROR_HASH:=22dc17656b9e1e39ac30e40e61867f2d2d34550b0c1c89501596802c6872954b
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKG_MAINTAINER:=demo133

PKG_BUILD_DEPENDS:= \
	python3/host \
	python-build/host \
	python-installer/host \
	python-wheel/host \
	python-setuptools/host \
	python-flit-core/host \
	python-hatchling/host \
	python-poetry-core/host \
	python-packaging/host \
	python-pyproject-hooks/host \
	python-pip/host

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

# ============================================================
# 自定义 Build/Compile：显式构建 wheel 并安装
# 不再依赖 Py3Package 宏，避免它只安装不构建的问题
# ============================================================
define Build/Compile
	# 第一步：用 host python 构建 wheel
	cd $(PKG_BUILD_DIR) && \
		$(STAGING_DIR_HOSTPKG)/bin/python3 -m build \
			--wheel \
			--no-isolation \
			--outdir $(PKG_BUILD_DIR)/openwrt-build \
			.
	# 第二步：把 wheel 安装到 PKG_INSTALL_DIR
	$(STAGING_DIR_HOSTPKG)/bin/python3 -m installer \
		--overwrite-existing \
		--destdir $(PKG_INSTALL_DIR) \
		--no-compile-bytecode \
		--prefix /usr \
		$(PKG_BUILD_DIR)/openwrt-build/*.whl
endef

define Package/campusnet/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/campusnet $(1)/usr/bin/
endef

$(eval $(call BuildPackage,campusnet))
