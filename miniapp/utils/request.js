/**
 * 剧云榜 — 网络请求封装
 */
const app = getApp()

function request(options) {
  return new Promise((resolve, reject) => {
    const { url, method = 'GET', data = {}, needAuth = false } = options

    const header = {
      'Content-Type': 'application/json'
    }

    // 需要认证的接口添加token
    if (needAuth) {
      const token = app.globalData.token || wx.getStorageSync('token')
      if (token) {
        header['Authorization'] = 'Bearer ' + token
      }
    }

    wx.request({
      url: app.globalData.baseUrl + url,
      method,
      data,
      header,
      timeout: 15000,
      success(res) {
        if (res.statusCode === 200) {
          if (res.data.code === 200) {
            resolve(res.data.data)
          } else {
            reject(res.data)
          }
        } else if (res.statusCode === 401) {
          // token过期，重新登录
          app.autoLogin()
          reject({ code: 401, message: '请重新登录' })
        } else {
          reject({ code: res.statusCode, message: '请求失败' })
        }
      },
      fail(err) {
        reject({ code: -1, message: '网络异常，请检查网络连接' })
      }
    })
  })
}

// GET请求
function get(url, data = {}, needAuth = false) {
  return request({ url, method: 'GET', data, needAuth })
}

// POST请求
function post(url, data = {}, needAuth = true) {
  return request({ url, method: 'POST', data, needAuth })
}

// PUT请求
function put(url, data = {}, needAuth = true) {
  return request({ url, method: 'PUT', data, needAuth })
}

// DELETE请求
function del(url, data = {}, needAuth = true) {
  return request({ url, method: 'DELETE', data, needAuth })
}

module.exports = { request, get, post, put, del }
