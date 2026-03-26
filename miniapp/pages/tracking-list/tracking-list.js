const api = require('../../utils/request')
const { formatTimeAgo } = require('../../utils/format')

const app = getApp()

const EMPTY_TEXT = {
  watching: '还没有在追的剧哦',
  want_to_watch: '还没有想看的剧',
  watched: '还没有看完的剧',
  dropped: '没有弃剧记录'
}

Page({
  data: {
    darkMode: false,
    activeTab: 'watching',
    list: [],
    counts: { watching: 0, want_to_watch: 0, watched: 0, dropped: 0 },
    loading: true,
    emptyText: '还没有在追的剧哦',
    page: 1,
    hasMore: true
  },

  onLoad(options) {
    const tab = options.tab || 'watching'
    // Map short names from mine page
    const tabMap = { watching: 'watching', want: 'want_to_watch', watched: 'watched', dropped: 'dropped' }
    const activeTab = tabMap[tab] || tab
    this.setData({
      activeTab,
      emptyText: EMPTY_TEXT[activeTab],
      darkMode: app.globalData.themeMode === 'dark'
    })
    this.loadCounts()
    this.loadList()
  },

  onShow() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    Promise.all([this.loadCounts(), this.loadList()]).then(() => {
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.setData({ page: this.data.page + 1 })
      this.loadList(true)
    }
  },

  // 加载统计数
  async loadCounts() {
    try {
      const data = await api.get('/tracking/stats', {}, true)
      this.setData({
        counts: {
          watching: data.watching || 0,
          want_to_watch: data.want || data.want_to_watch || 0,
          watched: data.watched || 0,
          dropped: data.dropped || 0
        }
      })
    } catch (e) {
      console.error('加载统计失败', e)
    }
  },

  // 加载列表
  async loadList(append = false) {
    if (!append) this.setData({ loading: true })

    try {
      const data = await api.get('/tracking/list', {
        status: this.data.activeTab,
        page: this.data.page,
        limit: 20
      }, true)

      let list = (data.list || data || []).map(item => ({
        ...item,
        progress: item.total_episodes ? Math.round((item.current_ep || 0) / item.total_episodes * 100) : 0,
        update_time_display: item.updated_at ? formatTimeAgo(item.updated_at) : ''
      }))

      const newList = append ? [...this.data.list, ...list] : list

      this.setData({
        list: newList,
        loading: false,
        hasMore: list.length >= 20
      })
    } catch (e) {
      console.error('加载追剧列表失败', e)
      this.setData({ loading: false })
    }
  },

  // 切换Tab
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    if (tab === this.data.activeTab) return
    this.setData({
      activeTab: tab,
      emptyText: EMPTY_TEXT[tab],
      list: [],
      page: 1,
      hasMore: true
    })
    this.loadList()
  },

  // 更新观看进度
  updateProgress(e) {
    const { id, current, total } = e.currentTarget.dataset
    const items = []
    for (let i = 1; i <= (total || 50); i++) {
      items.push(`第${i}集`)
    }

    wx.showActionSheet({
      itemList: items.slice(current || 0, Math.min((current || 0) + 10, items.length)),
      success: async (res) => {
        const newEp = (current || 0) + res.tapIndex + 1
        try {
          await api.put(`/tracking/${id}`, { current_ep: newEp })
          wx.showToast({ title: `已更新到第${newEp}集`, icon: 'success' })
          this.loadList()
        } catch (e) {
          wx.showToast({ title: '更新失败', icon: 'none' })
        }
      }
    })
  },

  // 开始追剧
  async startWatching(e) {
    const id = e.currentTarget.dataset.id
    try {
      await api.put(`/tracking/${id}`, { status: 'watching' })
      wx.showToast({ title: '已开始追剧', icon: 'success' })
      this.loadCounts()
      this.loadList()
    } catch (e) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  // 移除追剧
  removeTracking(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认移除',
      content: '确定要从清单中移除吗？',
      success: async (res) => {
        if (res.confirm) {
          try {
            await api.del(`/tracking/${id}`)
            wx.showToast({ title: '已移除', icon: 'success' })
            this.loadCounts()
            this.loadList()
          } catch (e) {
            wx.showToast({ title: '移除失败', icon: 'none' })
          }
        }
      }
    })
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  goDiscover() {
    wx.switchTab({ url: '/pages/discover/discover' })
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 我的追剧',
      path: '/pages/tracking-list/tracking-list'
    }
  }
})
