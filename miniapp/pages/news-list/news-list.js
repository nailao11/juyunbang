const api = require('../../utils/request')
const { formatTimeAgo } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    darkMode: false,
    loading: true,
    currentCategory: '',
    categories: [
      { key: '', name: '全部' },
      { key: 'update', name: '剧集动态' },
      { key: 'rating', name: '口碑评分' },
      { key: 'data', name: '数据分析' },
      { key: 'industry', name: '行业资讯' },
      { key: 'celebrity', name: '艺人动态' }
    ],
    newsList: [],
    page: 1,
    hasMore: true
  },

  onLoad() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
    this.loadNews()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    this.loadNews().then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.setData({ page: this.data.page + 1 })
      this.loadNews(true)
    }
  },

  async loadNews(append = false) {
    if (!append) this.setData({ loading: true })

    try {
      const data = await api.get('/news/list', {
        category: this.data.currentCategory,
        page: this.data.page,
        limit: 20
      })

      let list = (data.list || data || []).map(item => ({
        ...item,
        time_display: formatTimeAgo(item.published_at || item.created_at)
      }))

      const newList = append ? [...this.data.newsList, ...list] : list

      this.setData({
        newsList: newList,
        loading: false,
        hasMore: list.length >= 20
      })
    } catch (e) {
      console.error('加载资讯失败', e)
      this.setData({ loading: false })
    }
  },

  switchCategory(e) {
    const category = e.currentTarget.dataset.category
    this.setData({ currentCategory: category, page: 1, newsList: [] })
    this.loadNews()
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/news-detail/news-detail?id=${id}` })
  }
})
