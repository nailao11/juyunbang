const app = getApp()

Page({
  data: {
    darkMode: false
  },

  onLoad() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  navigateTo(e) {
    wx.navigateTo({ url: e.currentTarget.dataset.url })
  },

  copyContact() {
    wx.setClipboardData({
      data: 'juyunbang@example.com',
      success: () => {
        wx.showToast({ title: '邮箱已复制', icon: 'success' })
      }
    })
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 关于我们',
      path: '/pages/about/about'
    }
  }
})
