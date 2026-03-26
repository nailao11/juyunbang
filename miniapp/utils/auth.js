/**
 * 认证工具模块
 * 处理登录状态检查、token管理、用户信息获取
 */

const app = getApp()

/**
 * 检查是否已登录
 */
function isLoggedIn() {
  return !!app.globalData.token
}

/**
 * 获取当前用户token
 */
function getToken() {
  return app.globalData.token || wx.getStorageSync('token') || ''
}

/**
 * 获取当前用户ID
 */
function getUserId() {
  return wx.getStorageSync('userId') || null
}

/**
 * 需要登录才能执行的操作，未登录则提示
 * @param {Function} callback 登录后执行的回调
 */
function requireLogin(callback) {
  if (isLoggedIn()) {
    callback && callback()
    return
  }

  wx.showModal({
    title: '提示',
    content: '该功能需要登录，是否立即登录？',
    confirmText: '去登录',
    success: (res) => {
      if (res.confirm) {
        login(callback)
      }
    }
  })
}

/**
 * 执行登录
 * @param {Function} callback 登录成功后的回调
 */
function login(callback) {
  wx.login({
    success: (res) => {
      if (!res.code) {
        wx.showToast({ title: '登录失败', icon: 'none' })
        return
      }
      wx.request({
        url: app.globalData.baseUrl + '/auth/login',
        method: 'POST',
        data: { code: res.code },
        success: (resp) => {
          if (resp.data && resp.data.code === 200 && resp.data.data) {
            const { token, user_id } = resp.data.data
            app.globalData.token = token
            wx.setStorageSync('token', token)
            wx.setStorageSync('userId', user_id)
            callback && callback()
          } else {
            wx.showToast({ title: '登录失败', icon: 'none' })
          }
        },
        fail: () => {
          wx.showToast({ title: '网络错误', icon: 'none' })
        }
      })
    },
    fail: () => {
      wx.showToast({ title: '登录失败', icon: 'none' })
    }
  })
}

/**
 * 退出登录
 */
function logout() {
  app.globalData.token = null
  app.globalData.userInfo = null
  wx.removeStorageSync('token')
  wx.removeStorageSync('userId')
}

module.exports = {
  isLoggedIn,
  getToken,
  getUserId,
  requireLogin,
  login,
  logout
}
