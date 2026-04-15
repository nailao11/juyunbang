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

  onShareAppMessage() {
    return {
      title: '剧云榜 — 关于我们',
      path: '/pages/about/about'
    }
  }
})
