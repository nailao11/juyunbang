const api = require('../../utils/request')
const { formatHeat } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    keyword: '',
    autoFocus: true,
    searched: false,
    loading: false,
    darkMode: false,
    statusBarHeight: 20,
    suggestList: [],
    hotList: [],
    historyList: [],
    resultList: [],
    totalCount: 0,
    page: 1,
    hasMore: true,
    // 选择模式：当上游页面（如 compare）以 events 方式拉起搜索时为 true
    pickMode: false
  },

  _suggestTimer: null,

  onLoad(options) {
    const systemInfo = app.globalData.systemInfo || wx.getSystemInfoSync()
    this.setData({
      statusBarHeight: systemInfo.statusBarHeight || 20,
      darkMode: app.globalData.themeMode === 'dark',
      pickMode: options && options.pick === '1'
    })
    this.loadHotSearch()
    this.loadHistory()
  },

  // 选中一部剧：如果处于选择模式则通过 eventChannel 回传给调用方，否则跳转详情
  _pickOrNavigate(drama) {
    if (this.data.pickMode) {
      const eventChannel = this.getOpenerEventChannel && this.getOpenerEventChannel()
      if (eventChannel && typeof eventChannel.emit === 'function') {
        eventChannel.emit('selectDrama', drama)
      }
      wx.navigateBack({ delta: 1 })
      return true
    }
    return false
  },

  // 加载热搜榜
  async loadHotSearch() {
    try {
      const data = await api.get('/search/hot')
      const raw = Array.isArray(data) ? data : (data && data.list) || []
      const hotList = raw.map(item => {
        // 兼容后端返回对象 {keyword, heat_value, drama_id} 或字符串
        if (typeof item === 'string') {
          return { keyword: item, heat_display: '' }
        }
        return {
          drama_id: item.drama_id,
          keyword: item.keyword || item.title || '',
          heat_display: item.heat_value ? formatHeat(item.heat_value) : ''
        }
      }).filter(x => x.keyword)
      this.setData({ hotList })
    } catch (e) {
      console.error('加载热搜失败', e)
    }
  },

  // 加载搜索历史
  loadHistory() {
    const history = wx.getStorageSync('searchHistory') || []
    this.setData({ historyList: history })
  },

  // 保存搜索历史
  saveHistory(keyword) {
    let history = wx.getStorageSync('searchHistory') || []
    history = history.filter(k => k !== keyword)
    history.unshift(keyword)
    if (history.length > 15) history = history.slice(0, 15)
    wx.setStorageSync('searchHistory', history)
    this.setData({ historyList: history })
  },

  // 清除搜索历史
  clearHistory() {
    wx.showModal({
      title: '提示',
      content: '确定清除搜索历史？',
      success: (res) => {
        if (res.confirm) {
          wx.removeStorageSync('searchHistory')
          this.setData({ historyList: [] })
        }
      }
    })
  },

  // 输入事件（带防抖）
  onInput(e) {
    const keyword = e.detail.value.trim()
    this.setData({ keyword, searched: false })

    if (this._suggestTimer) clearTimeout(this._suggestTimer)

    if (!keyword) {
      this.setData({ suggestList: [] })
      return
    }

    this._suggestTimer = setTimeout(() => {
      this.loadSuggest(keyword)
    }, 300)
  },

  // 加载搜索建议
  async loadSuggest(keyword) {
    try {
      const data = await api.get('/search/suggest', { keyword })
      this.setData({ suggestList: data.list || data || [] })
    } catch (e) {
      this.setData({ suggestList: [] })
    }
  },

  // 执行搜索
  async doSearch() {
    const keyword = this.data.keyword.trim()
    if (!keyword) return

    this.saveHistory(keyword)
    this.setData({
      searched: true,
      loading: true,
      suggestList: [],
      page: 1,
      resultList: []
    })

    try {
      const data = await api.get('/search', { keyword, page: 1, limit: 20 })
      const list = (data.list || data || []).map(item => ({
        ...item,
        heat_display: item.heat_value ? formatHeat(item.heat_value) : ''
      }))

      this.setData({
        resultList: list,
        totalCount: data.total || list.length,
        loading: false,
        hasMore: list.length >= 20
      })
    } catch (e) {
      console.error('搜索失败', e)
      this.setData({ loading: false })
      wx.showToast({ title: '搜索失败', icon: 'none' })
    }
  },

  // 加载更多
  onReachBottom() {
    if (!this.data.searched || !this.data.hasMore || this.data.loading) return
    this.setData({ page: this.data.page + 1, loading: true })

    api.get('/search', {
      keyword: this.data.keyword,
      page: this.data.page,
      limit: 20
    }).then(data => {
      const list = (data.list || data || []).map(item => ({
        ...item,
        heat_display: item.heat_value ? formatHeat(item.heat_value) : ''
      }))
      this.setData({
        resultList: [...this.data.resultList, ...list],
        loading: false,
        hasMore: list.length >= 20
      })
    }).catch(() => {
      this.setData({ loading: false })
    })
  },

  // 点击搜索建议
  tapSuggest(e) {
    const { keyword, id } = e.currentTarget.dataset
    if (id) {
      this.saveHistory(keyword)
      // 选择模式：把建议项整条回传
      const drama = (this.data.suggestList || []).find(s => String(s.id) === String(id))
      if (drama && this._pickOrNavigate(drama)) return
      wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
    } else {
      this.setData({ keyword })
      this.doSearch()
    }
  },

  // 点击历史
  tapHistory(e) {
    const keyword = e.currentTarget.dataset.keyword
    this.setData({ keyword })
    this.doSearch()
  },

  // 点击热搜
  tapHot(e) {
    const keyword = e.currentTarget.dataset.keyword
    this.setData({ keyword })
    this.doSearch()
  },

  // 清除关键词
  clearKeyword() {
    this.setData({
      keyword: '',
      searched: false,
      suggestList: [],
      resultList: []
    })
  },

  // 跳转详情（或选择模式下回传给上游页面）
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    const drama = (this.data.resultList || []).find(d => String(d.id) === String(id))
    if (drama && this._pickOrNavigate(drama)) return
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  // 返回
  goBack() {
    wx.navigateBack({ delta: 1 })
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 搜索',
      path: '/pages/search/search'
    }
  }
})
