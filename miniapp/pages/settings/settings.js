const app = getApp()

Page({
  data: {
    darkMode: false,
    themeMode: 'light',
    notifyUpdate: true,
    notifyHeat: false,
    notifyRank: false,
    defaultRankIndex: 0,
    rankOptions: ['热度榜', '播放量榜', '剧力指数榜', '讨论度榜'],
    cacheSize: '计算中...',
    isLoggedIn: false
  },

  onLoad() {
    this.setData({
      themeMode: app.globalData.themeMode || 'light',
      darkMode: app.globalData.themeMode === 'dark',
      isLoggedIn: !!app.globalData.token,
      notifyUpdate: wx.getStorageSync('notifyUpdate') !== false,
      notifyHeat: wx.getStorageSync('notifyHeat') === true,
      notifyRank: wx.getStorageSync('notifyRank') === true,
      defaultRankIndex: wx.getStorageSync('defaultRankIndex') || 0
    })
    this.calculateCache()
  },

  // 主题切换
  setTheme(e) {
    const theme = e.currentTarget.dataset.theme
    app.globalData.themeMode = theme
    wx.setStorageSync('themeMode', theme)
    this.setData({
      themeMode: theme,
      darkMode: theme === 'dark'
    })
    wx.showToast({ title: '主题已切换', icon: 'success' })
  },

  toggleNotifyUpdate(e) {
    const val = e.detail.value
    wx.setStorageSync('notifyUpdate', val)
    this.setData({ notifyUpdate: val })
  },

  toggleNotifyHeat(e) {
    const val = e.detail.value
    wx.setStorageSync('notifyHeat', val)
    this.setData({ notifyHeat: val })
  },

  toggleNotifyRank(e) {
    const val = e.detail.value
    wx.setStorageSync('notifyRank', val)
    this.setData({ notifyRank: val })
  },

  onDefaultRankChange(e) {
    const idx = Number(e.detail.value)
    wx.setStorageSync('defaultRankIndex', idx)
    this.setData({ defaultRankIndex: idx })
  },

  // 计算缓存大小
  calculateCache() {
    try {
      const res = wx.getStorageInfoSync()
      const sizeKB = res.currentSize || 0
      let display = ''
      if (sizeKB >= 1024) {
        display = (sizeKB / 1024).toFixed(1) + ' MB'
      } else {
        display = sizeKB + ' KB'
      }
      this.setData({ cacheSize: display })
    } catch (e) {
      this.setData({ cacheSize: '未知' })
    }
  },

  // 清除缓存
  clearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '将清除本地缓存数据，不影响账号信息',
      success: (res) => {
        if (res.confirm) {
          // 保留关键数据
          const token = wx.getStorageSync('token')
          const userId = wx.getStorageSync('userId')
          const theme = wx.getStorageSync('themeMode')

          wx.clearStorageSync()

          // 恢复关键数据
          if (token) wx.setStorageSync('token', token)
          if (userId) wx.setStorageSync('userId', userId)
          if (theme) wx.setStorageSync('themeMode', theme)

          this.calculateCache()
          wx.showToast({ title: '缓存已清除', icon: 'success' })
        }
      }
    })
  },

  // 检查更新
  checkUpdate() {
    const updateManager = wx.getUpdateManager()
    updateManager.onCheckForUpdate((res) => {
      if (res.hasUpdate) {
        updateManager.onUpdateReady(() => {
          wx.showModal({
            title: '更新提示',
            content: '新版本已下载，是否重启应用？',
            success: (r) => {
              if (r.confirm) updateManager.applyUpdate()
            }
          })
        })
      } else {
        wx.showToast({ title: '已是最新版本', icon: 'success' })
      }
    })
  },

  // 退出登录
  logout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          app.globalData.token = null
          app.globalData.userInfo = null
          wx.removeStorageSync('token')
          wx.removeStorageSync('userId')
          wx.removeStorageSync('userInfo')
          this.setData({ isLoggedIn: false })
          wx.showToast({ title: '已退出', icon: 'success' })
        }
      }
    })
  },

  navigateTo(e) {
    wx.navigateTo({ url: e.currentTarget.dataset.url })
  }
})
