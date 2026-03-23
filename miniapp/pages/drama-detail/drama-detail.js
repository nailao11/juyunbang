const api = require('../../utils/request')
const { formatNumber, formatHeat, formatChange } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    dramaId: '',
    drama: {},
    heatData: {},
    powerData: {
      total: 0,
      dimensions: []
    },
    playData: {},
    socialData: [],
    relatedList: [],
    trackingStatus: '',
    showFullSynopsis: false,
    scrolled: false,
    darkMode: false,
    statusBarHeight: 20
  },

  onLoad(options) {
    const systemInfo = app.globalData.systemInfo || wx.getSystemInfoSync()
    this.setData({
      dramaId: options.id || '',
      statusBarHeight: systemInfo.statusBarHeight || 20,
      darkMode: app.globalData.themeMode === 'dark'
    })

    if (options.id) {
      this.loadDramaDetail(options.id)
      this.loadHeatData(options.id)
      this.loadPowerData(options.id)
      this.loadPlayData(options.id)
      this.loadSocialData(options.id)
      this.loadRelated(options.id)
      this.loadTrackingStatus(options.id)
    }
  },

  onShow() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  onPageScroll(e) {
    this.setData({ scrolled: e.scrollTop > 200 })
  },

  // 加载剧集详情
  async loadDramaDetail(id) {
    try {
      const data = await api.get(`/drama/${id}`)
      // 计算星星数
      data.star_count = data.douban_score ? Math.round(data.douban_score / 2) : 0
      // 处理类型标签
      if (data.genre && typeof data.genre === 'string') {
        data.genres = data.genre.split(/[,，/]/).map(s => s.trim()).filter(Boolean)
      } else {
        data.genres = data.genres || []
      }
      this.setData({ drama: data })

      // 更新标题
      wx.setNavigationBarTitle({ title: data.title || '剧集详情' })
    } catch (e) {
      console.error('加载剧集详情失败', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  // 加载实时热度
  async loadHeatData(id) {
    try {
      const data = await api.get(`/drama/${id}/heat`)
      this.setData({
        heatData: {
          current: formatHeat(data.current_heat),
          today_peak: formatHeat(data.today_peak),
          rank: data.rank,
          trend: data.trend || 'flat',
          change_display: data.change_pct ? formatChange(data.change_pct) : '-'
        }
      })
    } catch (e) {
      console.error('加载热度数据失败', e)
    }
  },

  // 加载剧力指数
  async loadPowerData(id) {
    try {
      const data = await api.get(`/drama/${id}/power-index`)
      this.setData({
        powerData: {
          total: data.total || 0,
          dimensions: data.dimensions || [
            { name: '热度', value: data.heat_score || 0 },
            { name: '口碑', value: data.reputation_score || 0 },
            { name: '播放', value: data.play_score || 0 },
            { name: '讨论', value: data.discuss_score || 0 },
            { name: '媒体', value: data.media_score || 0 }
          ]
        }
      })
    } catch (e) {
      console.error('加载剧力指数失败', e)
    }
  },

  // 加载播放量
  async loadPlayData(id) {
    try {
      const data = await api.get(`/drama/${id}/play`)
      this.setData({
        playData: {
          total_display: formatNumber(data.total_play),
          today_display: formatNumber(data.today_play),
          avg_display: formatNumber(data.avg_daily_play),
          change_pct: data.change_pct ? formatChange(data.change_pct) : '-',
          trend: data.trend || 'flat'
        }
      })
    } catch (e) {
      console.error('加载播放数据失败', e)
    }
  },

  // 加载社交媒体数据
  async loadSocialData(id) {
    try {
      const data = await api.get(`/drama/${id}/social`)
      const list = (data.list || data || []).map(item => ({
        ...item,
        value_display: formatNumber(item.value),
        change_display: item.change_pct ? formatChange(item.change_pct) : '-'
      }))
      this.setData({ socialData: list })
    } catch (e) {
      console.error('加载社交数据失败', e)
      // 设置默认数据
      this.setData({
        socialData: [
          { platform: '微博', icon: '微', color: '#E6162D', metric: '话题阅读', value_display: '-', trend: 'flat', change_display: '-' },
          { platform: '抖音', icon: '抖', color: '#000000', metric: '相关播放', value_display: '-', trend: 'flat', change_display: '-' },
          { platform: '百度', icon: '百', color: '#2932E1', metric: '搜索指数', value_display: '-', trend: 'flat', change_display: '-' }
        ]
      })
    }
  },

  // 加载相关推荐
  async loadRelated(id) {
    try {
      const data = await api.get(`/drama/${id}/related`, { limit: 8 })
      this.setData({ relatedList: data.list || data || [] })
    } catch (e) {
      console.error('加载相关推荐失败', e)
    }
  },

  // 加载追剧状态
  async loadTrackingStatus(id) {
    try {
      const data = await api.get(`/user/tracking/${id}`, {}, true)
      this.setData({ trackingStatus: data.status || '' })
    } catch (e) {
      // 未登录或未追
    }
  },

  // 追剧/想看
  async toggleTracking(e) {
    const status = e.currentTarget.dataset.status
    const current = this.data.trackingStatus

    try {
      if (current === status) {
        // 取消
        await api.del(`/user/tracking/${this.data.dramaId}`)
        this.setData({ trackingStatus: '' })
        wx.showToast({ title: '已取消', icon: 'success' })
      } else {
        // 添加/更新
        await api.post('/user/tracking', {
          drama_id: this.data.dramaId,
          status: status
        })
        this.setData({ trackingStatus: status })
        const label = status === 'watching' ? '已加入追剧' : '已加入想看'
        wx.showToast({ title: label, icon: 'success' })
      }
    } catch (e) {
      wx.showToast({ title: '请先登录', icon: 'none' })
    }
  },

  // 展开/收起简介
  toggleSynopsis() {
    this.setData({ showFullSynopsis: !this.data.showFullSynopsis })
  },

  // 去写笔记
  goNotes() {
    wx.navigateTo({
      url: `/pages/notes/notes?drama_id=${this.data.dramaId}&title=${this.data.drama.title || ''}`
    })
  },

  // 返回
  goBack() {
    wx.navigateBack({ delta: 1 })
  },

  // 跳转详情（相关推荐）
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.redirectTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  // 分享
  onShareTap() {
    // 触发分享菜单
  },

  onShareAppMessage() {
    return {
      title: `${this.data.drama.title || '剧集详情'} - 剧云榜`,
      path: `/pages/drama-detail/drama-detail?id=${this.data.dramaId}`
    }
  }
})
