const api = require('../../utils/request')
const { formatTimeAgo, formatHeat } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    darkMode: false,
    loading: true,
    article: {}
  },

  onLoad(options) {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
    if (options.id) {
      this.loadArticle(options.id)
    }
  },

  async loadArticle(id) {
    this.setData({ loading: true })
    try {
      const data = await api.get(`/news/${id}`)
      data.time_display = formatTimeAgo(data.published_at || data.created_at)

      // 处理相关剧集热度显示
      if (data.related_dramas) {
        data.related_dramas = data.related_dramas.map(d => ({
          ...d,
          heat_display: d.heat_value ? formatHeat(d.heat_value) : ''
        }))
      }

      this.setData({ article: data, loading: false })
      wx.setNavigationBarTitle({ title: data.title || '资讯详情' })
    } catch (e) {
      console.error('加载资讯详情失败', e)
      this.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  onShareAppMessage() {
    return {
      title: this.data.article.title || '剧云榜资讯',
      path: `/pages/news-detail/news-detail?id=${this.data.article.id}`
    }
  }
})
