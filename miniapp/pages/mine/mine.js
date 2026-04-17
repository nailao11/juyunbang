const api = require('../../utils/request')

const app = getApp()

Page({
  data: {
    userInfo: {},
    stats: {
      dramaCount: '-',
      platformCount: 4
    },
    darkMode: false
  },

  onLoad() {
    this.checkDarkMode()
  },

  onShow() {
    this.checkDarkMode()
    this.loadUserInfo()
    this.loadStats()
  },

  checkDarkMode() {
    const darkMode = app.globalData.themeMode === 'dark'
    this.setData({ darkMode })
    wx.setBackgroundColor({
      backgroundColor: darkMode ? '#171923' : '#f4f5f7',
      backgroundColorTop: darkMode ? '#171923' : '#f4f5f7',
      backgroundColorBottom: darkMode ? '#171923' : '#f4f5f7'
    })
  },

  // 加载用户信息
  async loadUserInfo() {
    try {
      const data = await api.get('/auth/profile', {}, true)
      this.setData({ userInfo: data || {} })
    } catch (e) {
      // 未登录时使用本地缓存
      const cached = wx.getStorageSync('userInfo')
      if (cached) {
        this.setData({ userInfo: cached })
      }
    }
  },

  // 加载数据概览
  async loadStats() {
    try {
      const data = await api.get('/system/stats')
      this.setData({
        'stats.dramaCount': (data && data.drama_count) || '-',
        'stats.platformCount': (data && data.platform_count) || 4
      })
    } catch (e) {
      console.error('加载数据概览失败', e)
    }
  },

  // 获取用户信息
  getUserProfile() {
    wx.getUserProfile({
      desc: '用于完善个人资料',
      success: (res) => {
        const wxInfo = res.userInfo
        const userInfo = {
          ...this.data.userInfo,
          nickname: wxInfo.nickName,
          avatar_url: wxInfo.avatarUrl
        }
        this.setData({ userInfo })
        wx.setStorageSync('userInfo', userInfo)
        // 同步到服务器
        api.post('/auth/profile', {
          nickname: wxInfo.nickName,
          avatar_url: wxInfo.avatarUrl
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
        this.setData({ 'userInfo.avatar_url': tempPath })
        // 上传头像
        wx.uploadFile({
          url: app.globalData.baseUrl + '/auth/avatar',
          filePath: tempPath,
          name: 'avatar',
          header: {
            'Authorization': 'Bearer ' + (app.globalData.token || '')
          },
          success: (uploadRes) => {
            try {
              const resp = JSON.parse(uploadRes.data)
              const newUrl = resp && resp.data && resp.data.url
              if (newUrl) {
                this.setData({ 'userInfo.avatar_url': newUrl })
              }
            } catch (e) {}
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

  // 通用导航
  navigateTo(e) {
    const url = e.currentTarget.dataset.url
    wx.navigateTo({ url })
  },

  onShareAppMessage() {
    return {
      title: '热剧榜 — 全平台剧集热度数据助手',
      path: '/pages/index/index'
    }
  }
})
