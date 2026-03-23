const api = require('../../utils/request')

const app = getApp()

Page({
  data: {
    userInfo: {},
    stats: {
      watching: 0,
      want: 0,
      watched: 0
    },
    watchingPercent: 0,
    wantPercent: 0,
    watchedPercent: 0,
    darkMode: false
  },

  onLoad() {
    this.checkDarkMode()
  },

  onShow() {
    this.checkDarkMode()
    this.loadUserInfo()
    this.loadTrackingStats()
  },

  checkDarkMode() {
    const darkMode = app.globalData.themeMode === 'dark'
    this.setData({ darkMode })
  },

  // 加载用户信息
  async loadUserInfo() {
    try {
      const data = await api.get('/user/profile', {}, true)
      this.setData({ userInfo: data || {} })
    } catch (e) {
      // 未登录时使用本地缓存
      const cached = wx.getStorageSync('userInfo')
      if (cached) {
        this.setData({ userInfo: cached })
      }
    }
  },

  // 加载追剧统计
  async loadTrackingStats() {
    try {
      const data = await api.get('/user/tracking/stats', {}, true)
      const stats = data || { watching: 0, want: 0, watched: 0 }
      const total = stats.watching + stats.want + stats.watched
      const max = Math.max(total, 1)

      this.setData({
        stats,
        watchingPercent: Math.round((stats.watching / max) * 100),
        wantPercent: Math.round((stats.want / max) * 100),
        watchedPercent: Math.round((stats.watched / max) * 100)
      })
    } catch (e) {
      console.error('加载追剧统计失败', e)
    }
  },

  // 获取用户信息
  getUserProfile() {
    wx.getUserProfile({
      desc: '用于完善个人资料',
      success: (res) => {
        const userInfo = res.userInfo
        this.setData({ userInfo })
        wx.setStorageSync('userInfo', userInfo)
        // 同步到服务器
        api.post('/user/profile', {
          nickname: userInfo.nickName,
          avatar: userInfo.avatarUrl
        }).catch(() => {})
      },
      fail: () => {
        wx.showToast({ title: '授权取消', icon: 'none' })
      }
    })
  },

  // 选择头像
  chooseAvatar() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => {
        const tempPath = res.tempFiles[0].tempFilePath
        this.setData({ 'userInfo.avatar': tempPath })
        // 上传头像
        wx.uploadFile({
          url: app.globalData.baseUrl + '/user/avatar',
          filePath: tempPath,
          name: 'avatar',
          header: {
            'Authorization': 'Bearer ' + (app.globalData.token || '')
          },
          success: () => {
            wx.showToast({ title: '头像已更新', icon: 'success' })
          }
        })
      }
    })
  },

  // 切换深色模式
  toggleDarkMode(e) {
    const darkMode = e.detail.value
    app.globalData.themeMode = darkMode ? 'dark' : 'light'
    wx.setStorageSync('themeMode', app.globalData.themeMode)
    this.setData({ darkMode })
  },

  // 跳转追剧清单
  goTrackingList(e) {
    const tab = e.currentTarget.dataset.tab || ''
    wx.navigateTo({ url: `/pages/tracking-list/tracking-list?tab=${tab}` })
  },

  // 通用导航
  navigateTo(e) {
    const url = e.currentTarget.dataset.url
    wx.navigateTo({ url })
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 - 全平台追剧数据助手',
      path: '/pages/index/index'
    }
  }
})
