const api = require('../../utils/request')

const app = getApp()

Page({
  data: {
    darkMode: false,
    feedbackType: '',
    content: '',
    contact: '',
    images: [],
    canSubmit: false,
    types: [
      { key: 'bug', name: '问题反馈', emoji: '🐛' },
      { key: 'feature', name: '功能建议', emoji: '💡' },
      { key: 'data', name: '数据问题', emoji: '📊' },
      { key: 'other', name: '其他', emoji: '💬' }
    ]
  },

  onLoad() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  selectType(e) {
    this.setData({ feedbackType: e.currentTarget.dataset.type })
    this.checkCanSubmit()
  },

  onContentInput(e) {
    this.setData({ content: e.detail.value })
    this.checkCanSubmit()
  },

  onContactInput(e) {
    this.setData({ contact: e.detail.value })
  },

  checkCanSubmit() {
    const canSubmit = this.data.feedbackType && this.data.content.trim().length >= 10
    this.setData({ canSubmit })
  },

  addImage() {
    wx.chooseMedia({
      count: 3 - this.data.images.length,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => {
        const paths = res.tempFiles.map(f => f.tempFilePath)
        this.setData({ images: [...this.data.images, ...paths] })
      }
    })
  },

  removeImage(e) {
    const idx = e.currentTarget.dataset.index
    const images = [...this.data.images]
    images.splice(idx, 1)
    this.setData({ images })
  },

  async submit() {
    if (!this.data.canSubmit) return

    wx.showLoading({ title: '提交中...' })

    try {
      // 上传图片
      const imageUrls = []
      for (const path of this.data.images) {
        try {
          const uploadRes = await new Promise((resolve, reject) => {
            wx.uploadFile({
              url: app.globalData.baseUrl + '/system/upload/image',
              filePath: path,
              name: 'file',
              header: { 'Authorization': 'Bearer ' + (app.globalData.token || '') },
              success: (res) => resolve(JSON.parse(res.data)),
              fail: reject
            })
          })
          if (uploadRes.data && uploadRes.data.url) {
            imageUrls.push(uploadRes.data.url)
          }
        } catch (e) {
          // 图片上传失败忽略
        }
      }

      await api.post('/system/feedback', {
        type: this.data.feedbackType,
        content: this.data.content,
        contact: this.data.contact,
        images: imageUrls
      })

      wx.hideLoading()
      wx.showToast({ title: '感谢您的反馈！', icon: 'success' })

      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '提交失败，请重试', icon: 'none' })
    }
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 意见反馈',
      path: '/pages/feedback/feedback'
    }
  }
})
