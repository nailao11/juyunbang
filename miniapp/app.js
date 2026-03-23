App({
  globalData: {
    userInfo: null,
    token: null,
    baseUrl: 'https://api.sqnl8.cn/api/v1',
    themeMode: 'light', // light / dark / auto
    systemInfo: null
  },

  onLaunch() {
    // 获取系统信息
    const systemInfo = wx.getSystemInfoSync()
    this.globalData.systemInfo = systemInfo

    // 读取本地存储的token
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
    }

    // 读取主题设置
    const theme = wx.getStorageSync('themeMode')
    if (theme) {
      this.globalData.themeMode = theme
    }

    // 自动登录
    this.autoLogin()
  },

  autoLogin() {
    wx.login({
      success: (res) => {
        if (res.code) {
          wx.request({
            url: this.globalData.baseUrl + '/auth/login',
            method: 'POST',
            data: { code: res.code },
            success: (resp) => {
              if (resp.data.code === 200) {
                const { token, user_id } = resp.data.data
                this.globalData.token = token
                wx.setStorageSync('token', token)
                wx.setStorageSync('userId', user_id)
              }
            }
          })
        }
      }
    })
  }
})
